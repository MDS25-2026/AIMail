package main

import (
	"regexp"
	"strings"
	"unicode"
)

// Malaysian and Chinese names the English NER model misses, and the Malay prose it mistakes for names
// (specs/features/multilingual-masking.md). The patterns match backend/app/core/name_patterns.py, which
// hides names in text a person types; Presidio runs them as Python regexes, case-blind unless (?-i:).

const (
	nameCap  = `[A-Z][\w'’-]*`
	nameCaps = nameCap + `(?:\s+` + nameCap + `){0,2}`
	// Patronymic and lineage connectors that sit inside a name, written in lower case.
	nameConnector = `(?:bin|binti|binte|bte|bt\.?|a/l|a/p|s/o|d/o|anak|ak\.?)`
	nameLineage   = `Tengku|Tunku|Ungku|Raja|Syed|Sayyid|Sharifah|Syarifah|Wan|Nik|Megat|Puteri|Che|Abang|Awang|Dayang`
	nameGivenLead = `Muhammad|Mohammad|Mohamad|Mohamed|Mohd\.?|Muhd\.?|Md\.?|Abdul|Abd\.?|Nur|Nurul|Siti|Noor|Nor`
	hanSurnames   = "陈陳林黄黃张張李王吴吳刘劉蔡杨楊许許郑鄭谢謝洪郭邱曾廖赖賴徐周叶葉苏蘇庄莊吕呂江何萧蕭罗羅高潘朱钟鍾" +
		"游彭胡施沈余卢盧梁赵趙颜顏柯翁魏孙孫戴范方宋邓鄧杜傅侯曹薛丁卓阮马馬董温溫唐蓝藍石蒋蔣古纪紀姚连連" +
		"冯馮欧歐程汤湯田康姜白汪邹鄒尤巫黎涂龚龔严嚴韩韓袁金童陆陸夏柳邵钱錢伍"
	// Words that start with a surname character but are never a name: "thanks" in a sign-off above all.
	hanName    = `(?!谢谢|謝謝|周末|周一|周二|周三|周四|周五|周六|周日|高兴|高興|方便|马上|馬上|余下)[` + hanSurnames + `][\u4e00-\u9fff]{1,2}`
	hanAddress = `先生|小姐|女士|太太|夫人|老师|老師|医生|醫生|经理|經理|主任|博士|同学|同學|律师|律師`
	// A name is scored above the 0.6 threshold on its shape alone.
	nameScore = 0.85
)

// nameRecognizers find names by shape, as Presidio ad-hoc recognizers alongside its own model.
var nameRecognizers = []presidioRecognizer{
	{
		Name:              "MY_NAME_RECOGNIZER",
		SupportedLanguage: "en",
		SupportedEntity:   "PERSON",
		Patterns: []presidioPattern{
			{Name: "patronymic", Regex: `(?-i:(?:` + nameCap + `\s+){0,2}` + nameCap + `\s+` + nameConnector + `\s+` + nameCaps + `)`, Score: nameScore},
			{Name: "lineage", Regex: `(?-i:(?<!\w)(?:` + nameLineage + `)\s+` + nameCaps + `)`, Score: nameScore},
			{Name: "given_lead", Regex: `(?-i:(?<!\w)(?:` + nameGivenLead + `)\s+` + nameCaps + `)`, Score: nameScore},
		},
	},
	{
		Name:              "ZH_NAME_RECOGNIZER",
		SupportedLanguage: "en",
		SupportedEntity:   "PERSON",
		// Chinese has no spaces or capitals, so a surname counts as a name only where a name goes: before
		// a form of address, after "I am" or "contact", or alone on a line (a sign-off).
		Patterns: []presidioPattern{
			{Name: "zh_before_address", Regex: hanName + `(?=` + hanAddress + `)`, Score: nameScore},
			{Name: "zh_after_intro", Regex: `(?<=我是|我叫|联系|聯繫|聯絡|联络)` + hanName, Score: nameScore},
			{Name: "zh_after_word", Regex: `(?<=[致给給请請找由与與跟和])` + hanName, Score: nameScore},
			{Name: "zh_own_line", Regex: `(?m)^` + hanName + `(?=[，,:：]?[ \t]*$)`, Score: nameScore},
			{Name: "zh_greeting", Regex: `(?m)^` + hanName + `(?=[，,][ \t]*(?:您好|你好))`, Score: nameScore},
		},
	},
}

// Common Malay words, and job and department words, that the English model labels as names. A span
// made only of these is prose, not a person.
var malayProse = setOf(
	"saya", "ingin", "yang", "akan", "anda", "ini", "itu", "dan", "di", "ke", "dari", "daripada", "kepada",
	"untuk", "dengan", "boleh", "tahu", "berapa", "hari", "cuti", "tahunan", "masih", "berbaki", "tahun",
	"perhatian", "terima", "kasih", "salam", "sejahtera", "benar", "kerja", "kerja-kerja", "mohon", "memohon",
	"urusan", "keluarga", "kampung", "tempoh", "sepanjang", "diserahkan", "selamat", "pagi", "petang",
	"hormat", "sila", "maklum", "maklumkan", "adalah", "ada", "tidak", "sudah", "telah", "juga", "atau",
	"bagi", "oleh", "pada", "dalam", "kami", "kita", "mereka", "beliau", "dia", "kerana", "hingga", "sampai",
	"mesyuarat", "laporan", "bayaran", "invois", "pesanan", "permohonan", "makluman", "segera", "baik",
	"encik", "puan", "cik", "tuan", "dato", "datuk", "datin", "haji", "hajah",
	"eksekutif", "kewangan", "pengurus", "jabatan", "bahagian", "pegawai", "kanan", "penolong", "ketua",
	"pengarah", "pentadbiran", "sumber", "manusia", "akaun", "jualan", "pemasaran", "operasi",
)

// Lower-case words that belong inside a name ("Siti binti Ali", "Ludwig van Beethoven").
var nameParticles = setOf("bin", "binti", "binte", "bte", "bt", "bt.", "a/l", "a/p", "s/o", "d/o", "anak", "ak",
	"ak.", "van", "von", "de", "da", "del", "della", "le", "la", "du", "dos", "al")

var nameEntities = setOf("PERSON", "ORGANIZATION", "LOCATION")

func setOf(words ...string) map[string]bool {
	set := make(map[string]bool, len(words))
	for _, word := range words {
		set[word] = true
	}
	return set
}

type wordSpan struct {
	start, end int // rune offsets, trailing punctuation excluded
	text       string
}

// nameShapedOnly narrows each name, place or organisation hit to the runs of words that look like one:
// capitalised and not common Malay, or written in Chinese characters. "Saya ingin" and "cuti tahunan"
// drop out; "Farid", "Nurul Huda" and 陈伟明 stay. Other entities pass through untouched.
func nameShapedOnly(text string, results []presidioResult) []presidioResult {
	runes := []rune(text)
	kept := make([]presidioResult, 0, len(results))
	for _, r := range results {
		if !nameEntities[r.EntityType] || r.Start < 0 || r.End > len(runes) || r.Start >= r.End {
			kept = append(kept, r)
			continue
		}
		for _, run := range nameRuns(runes, r.Start, r.End) {
			kept = append(kept, presidioResult{EntityType: r.EntityType, Start: run[0], End: run[1], Score: r.Score})
		}
	}
	return kept
}

// nameRuns are the name-shaped stretches of runes[start:end], a particle joining two name words.
func nameRuns(runes []rune, start, end int) [][2]int {
	var runs [][2]int
	var current []wordSpan
	flush := func() {
		for len(current) > 0 && nameParticles[strings.ToLower(current[len(current)-1].text)] {
			current = current[:len(current)-1] // a run never ends on "bin"
		}
		if len(current) > 0 {
			runs = append(runs, [2]int{current[0].start, current[len(current)-1].end})
		}
		current = nil
	}
	for _, word := range words(runes, start, end) {
		switch {
		case isNameWord(word.text):
			current = append(current, word)
		case len(current) > 0 && nameParticles[strings.ToLower(word.text)]:
			current = append(current, word)
		default:
			flush()
		}
	}
	flush()
	return runs
}

var placeholderWordRe = regexp.MustCompile(`^(?:PERSON|EMAIL|PHONE|IC|PASSPORT|ACCOUNT|CARD|LOCATION|ORG)_\d+$`)

func isNameWord(word string) bool {
	if word == "" || malayProse[strings.ToLower(word)] || placeholderWordRe.MatchString(word) {
		return false
	}
	first := []rune(word)[0]
	return unicode.IsUpper(first) || unicode.Is(unicode.Han, first)
}

// words splits runes[start:end] at spaces, trimming punctuation from each word's ends.
func words(runes []rune, start, end int) []wordSpan {
	var spans []wordSpan
	isEdge := func(r rune) bool { return unicode.IsPunct(r) && r != '\'' && r != '’' && r != '/' }
	for i := start; i < end; {
		for i < end && unicode.IsSpace(runes[i]) {
			i++
		}
		j := i
		for j < end && !unicode.IsSpace(runes[j]) {
			j++
		}
		s, e := i, j
		for s < e && isEdge(runes[s]) {
			s++
		}
		for e > s && isEdge(runes[e-1]) {
			e--
		}
		if s < e {
			spans = append(spans, wordSpan{start: s, end: e, text: string(runes[s:e])})
		}
		i = j
	}
	return spans
}
