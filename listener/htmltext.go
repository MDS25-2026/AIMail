package main

import (
	"regexp"
	"strconv"
	"strings"

	"golang.org/x/net/html"
	"golang.org/x/net/html/atom"
)

// A table row reads "a | b" only when every cell is this short and on one line; longer cells are
// a layout table (newsletters build whole pages from them), where pipes would be noise.
const maxInlineCellChars = 60

var (
	// Spaces, tabs, newlines and no-break spaces inside running text are all one space.
	inlineSpaceRe = regexp.MustCompile(`[ \t\r\n\x{00A0}\x{200B}]+`)
	blankLineRe   = regexp.MustCompile(`\n{3,}`)
	spaceAroundRe = regexp.MustCompile(`[ \t\x{00A0}]*\n[ \t\x{00A0}]*`)
	// Each starts on a new line. Gmail writes every line as a <div>, so these never add a blank line.
	lineElements = map[atom.Atom]bool{
		atom.Div: true, atom.Table: true, atom.Tbody: true, atom.Thead: true, atom.Tfoot: true,
		atom.Ul: true, atom.Ol: true, atom.Section: true, atom.Article: true, atom.Header: true,
		atom.Footer: true, atom.Center: true, atom.Address: true, atom.Form: true, atom.Dl: true,
		atom.Dt: true, atom.Dd: true, atom.Td: true, atom.Th: true,
	}
	// Paragraphs as browsers space them: a blank line around each.
	paragraphElements = map[atom.Atom]bool{
		atom.P: true, atom.H1: true, atom.H2: true, atom.H3: true, atom.H4: true, atom.H5: true,
		atom.H6: true, atom.Hr: true,
	}
	// Code, metadata and images carry no prose. Comments, which hold Outlook's <!--[if mso]>
	// blocks, are never text nodes, so they drop out without a rule.
	skippedElements = map[atom.Atom]bool{
		atom.Script: true, atom.Style: true, atom.Head: true, atom.Title: true, atom.Meta: true,
		atom.Img: true, atom.Svg: true, atom.Template: true, atom.Noscript: true,
	}
)

// htmlToText turns an email's HTML into prose that reads the way the sender laid it out, for the
// masker and the dashboard (specs/features/readable-emails.md). Names stay in sentences, never next
// to markup: that is what kept Presidio's recall up when HTML was stripped by regex.
func htmlToText(markup string) string {
	root, err := html.Parse(strings.NewReader(markup))
	if err != nil {
		return ""
	}
	w := &textWriter{}
	w.children(root, false)
	return tidyLines(w.out.String())
}

type textWriter struct {
	out strings.Builder
}

// newline ends the current line unless it already ended; breaks never pile up from nesting.
func (w *textWriter) newline() {
	text := w.out.String()
	if text != "" && !strings.HasSuffix(strings.TrimRight(text, " "), "\n") {
		w.out.WriteString("\n")
	}
}

func (w *textWriter) blankLine() {
	w.newline()
	if !strings.HasSuffix(w.out.String(), "\n\n") && w.out.Len() > 0 {
		w.out.WriteString("\n")
	}
}

func (w *textWriter) children(node *html.Node, isPre bool) {
	for child := node.FirstChild; child != nil; child = child.NextSibling {
		w.node(child, isPre)
	}
}

func (w *textWriter) node(node *html.Node, isPre bool) {
	switch node.Type {
	case html.TextNode:
		w.text(node.Data, isPre)
	case html.ElementNode:
		w.element(node, isPre)
	default:
		w.children(node, isPre)
	}
}

func (w *textWriter) text(text string, isPre bool) {
	if isPre {
		w.out.WriteString(text)
		return
	}
	w.out.WriteString(inlineSpaceRe.ReplaceAllString(text, " "))
}

func (w *textWriter) element(node *html.Node, isPre bool) {
	if skippedElements[node.DataAtom] || isOfficeTag(node) {
		return
	}
	switch node.DataAtom {
	case atom.Br:
		w.out.WriteString("\n")
	case atom.A:
		w.out.WriteString(linkText(node, isPre))
	case atom.Li:
		w.newline()
		w.out.WriteString(listMarker(node))
		w.children(node, isPre)
		w.newline()
	case atom.Tr:
		w.newline()
		w.out.WriteString(rowText(node, isPre))
		w.newline()
	case atom.Blockquote:
		w.blankLine()
		w.out.WriteString(quoted(innerText(node, isPre)))
		w.blankLine()
	case atom.Pre:
		w.newline()
		w.children(node, true)
		w.newline()
	default:
		w.block(node, isPre)
	}
}

// block lays out an element by its kind. An empty one (Outlook's <p>&nbsp;</p>, Gmail's
// <div><br></div>) is how both clients write a blank line, so it becomes one.
func (w *textWriter) block(node *html.Node, isPre bool) {
	isParagraph := paragraphElements[node.DataAtom] && !isOutlookLine(node)
	isLine := lineElements[node.DataAtom] || isOutlookLine(node)
	switch {
	case isParagraph:
		w.blankLine()
	case isLine:
		w.newline()
	}
	before := w.out.Len()
	w.children(node, isPre)
	isEmpty := strings.TrimSpace(strings.ReplaceAll(w.out.String()[before:], " ", "")) == ""
	switch {
	case isParagraph:
		w.blankLine()
	case isLine && isEmpty && node.DataAtom != atom.Td && node.DataAtom != atom.Th:
		w.blankLine()
	case isLine:
		w.newline()
	}
}

// isOutlookLine is Outlook's paragraph, which it styles with no margin: one line, not a paragraph.
func isOutlookLine(node *html.Node) bool {
	return node.DataAtom == atom.P && strings.Contains(attr(node, "class"), "Mso")
}

// isOfficeTag is Outlook's own markup (<o:p>, <v:shape>, <xml>): spacing hacks and drawing data.
func isOfficeTag(node *html.Node) bool {
	return node.DataAtom == 0 && (strings.Contains(node.Data, ":") || node.Data == "xml")
}

// linkText keeps where a link points, as text: the agent's phishing check reads it.
func linkText(node *html.Node, isPre bool) string {
	label := strings.TrimSpace(inlineSpaceRe.ReplaceAllString(innerText(node, isPre), " "))
	href := attr(node, "href")
	isWeb := strings.HasPrefix(href, "http://") || strings.HasPrefix(href, "https://")
	if !isWeb {
		return label
	}
	if label == "" {
		return href
	}
	if sameURL(label, href) {
		return label
	}
	return label + " (" + href + ")"
}

func sameURL(label, href string) bool {
	trim := func(s string) string {
		s = strings.TrimPrefix(strings.TrimPrefix(s, "https://"), "http://")
		return strings.TrimSuffix(strings.TrimPrefix(s, "www."), "/")
	}
	return trim(label) == trim(href)
}

func listMarker(item *html.Node) string {
	if item.Parent == nil || item.Parent.DataAtom != atom.Ol {
		return "- "
	}
	position := 1
	for sibling := item.PrevSibling; sibling != nil; sibling = sibling.PrevSibling {
		if sibling.DataAtom == atom.Li {
			position++
		}
	}
	return strconv.Itoa(position) + ". "
}

// rowText joins a data row's cells with " | " and gives a layout row's cells a line each.
func rowText(row *html.Node, isPre bool) string {
	var cells []string
	isInline := true
	for cell := row.FirstChild; cell != nil; cell = cell.NextSibling {
		if cell.DataAtom != atom.Td && cell.DataAtom != atom.Th {
			continue
		}
		text := innerText(cell, isPre)
		if text == "" {
			continue
		}
		isInline = isInline && !strings.Contains(text, "\n") && len([]rune(text)) <= maxInlineCellChars && !hasTable(cell)
		cells = append(cells, text)
	}
	if isInline {
		return strings.Join(cells, " | ")
	}
	return strings.Join(cells, "\n")
}

func hasTable(node *html.Node) bool {
	for child := node.FirstChild; child != nil; child = child.NextSibling {
		if child.DataAtom == atom.Table || hasTable(child) {
			return true
		}
	}
	return false
}

func innerText(node *html.Node, isPre bool) string {
	w := &textWriter{}
	w.children(node, isPre)
	return tidyLines(w.out.String())
}

func quoted(text string) string {
	lines := strings.Split(text, "\n")
	for i, line := range lines {
		lines[i] = strings.TrimSpace("> " + line)
	}
	return strings.Join(lines, "\n")
}

func attr(node *html.Node, name string) string {
	for _, a := range node.Attr {
		if strings.EqualFold(a.Key, name) {
			return strings.TrimSpace(a.Val)
		}
	}
	return ""
}

// tidyLines trims each line, drops lines that are only spaces (Outlook's &nbsp; paragraphs), and
// keeps at most one blank line between paragraphs.
func tidyLines(text string) string {
	text = spaceAroundRe.ReplaceAllString(text, "\n")
	text = blankLineRe.ReplaceAllString(text, "\n\n")
	return strings.TrimSpace(text)
}
