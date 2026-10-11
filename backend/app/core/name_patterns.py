"""Malaysian name shapes the English NER model misses, found by rule (specs/features/privacy-gaps.md).

Malay patronymics (bin, binti, bt), Indian (a/l, a/p, s/o, d/o), Iban and Bidayuh (anak, ak), hereditary
prefixes that belong to the name (Tengku, Syed, Wan), common Malay given-name leads (Muhammad, Siti),
Chinese surnames written first, the name after a title (Encik, Datuk, Tan Sri), Indian initials
("R. Kumar"), and Chinese characters before a form of address (陈先生). Over-matching is safe: a hidden
word comes back after the model answers; under-matching sends a name.
"""

import re

_CAP = r"[A-Z][\w'’-]*"
_CAPS = rf"{_CAP}(?:\s+{_CAP}){{0,2}}"
_CONNECTOR = r"(?i:bin|binti|binte|bte|bt\.?|a/l|a/p|s/o|d/o|anak\s+lelaki|anak\s+perempuan|anak|ak\.?)"
# Hereditary prefixes are part of the name, so they are hidden with it.
_LINEAGE = (r"Tengku|Tunku|Ungku|Raja|Syed|Sayyid|Sharifah|Syarifah|Wan|Nik|Megat|Puteri|Che|Abang|Awang|"
            r"Dayang")
_GIVEN_LEADS = r"Muhammad|Mohammad|Mohamad|Mohamed|Mohd\.?|Muhd\.?|Md\.?|Abdul|Abd\.?|Nur|Nurul|Siti|Noor|Nor"
_TITLES = (r"Encik|En\.|Cik|Puan|Pn\.|Tuan|Tn\.|Haji|Hj\.?|Hajah|Hjh\.?|Dato'?|Dato’|Datuk|Datin|Tan\s+Sri|"
           r"Puan\s+Sri|Toh\s+Puan|Tun|Dr\.?|Prof\.?|Ir\.?|Ts\.?|Ustaz|Ustazah|Cikgu|Mr\.?|Mrs\.?|Ms\.?|"
           r"Mdm\.?|Madam|Miss|Sir")
_CHINESE_SURNAMES = (
    r"Tan|Lim|Lee|Ng|Wong|Chan|Ong|Goh|Teh|Tee|Chong|Chin|Chew|Choo|Chua|Cheah|Cheng|Chia|Chiew|Foo|Gan|Heng|"
    r"Hew|Ho|Hoo|Kang|Khoo|Koh|Kok|Kwan|Kwok|Lai|Lam|Lau|Leong|Leow|Liang|Liew|Lok|Loh|Low|Mah|Neo|Ooi|Pang|"
    r"Phang|Poh|Quek|Seah|Sim|Siow|Soh|Tay|Tham|Toh|Wee|Yap|Yeo|Yeoh|Yew|Yip|Yong|Zhang|Chen|Wang|Liu|Huang"
)
_HAN_SURNAMES = (
    "陈陳林黄黃张張李王吴吳刘劉蔡杨楊许許郑鄭谢謝洪郭邱曾廖赖賴徐周叶葉苏蘇庄莊吕呂江何萧蕭罗羅高潘朱钟鍾"
    "游彭胡施沈余卢盧梁赵趙颜顏柯翁魏孙孫戴范方宋邓鄧杜傅侯曹薛丁卓阮马馬董温溫唐蓝藍石蒋蔣古纪紀姚连連"
    "冯馮欧歐程汤湯田康姜白汪邹鄒尤巫黎涂龚龔严嚴韩韓袁金童陆陸夏柳邵钱錢伍"
)
_HAN_ADDRESS = "先生|小姐|女士|太太|夫人|老师|老師|医生|醫生|经理|經理|主任|博士|同学|同學|律师|律師|总|總"

_PATTERNS = (
    re.compile(rf"(?:{_CAP}\s+){{0,2}}{_CAP}\s+{_CONNECTOR}\s+{_CAPS}"),
    re.compile(rf"(?<!\w)(?:{_LINEAGE})\s+{_CAPS}"),
    re.compile(rf"(?<!\w)(?:{_GIVEN_LEADS})\s+{_CAPS}"),
    re.compile(rf"(?<!\w)(?:{_CHINESE_SURNAMES})(?!\s+Sri\b)\s+{_CAP}(?:\s+{_CAP})?"),
    re.compile(r"(?<![\w.])(?:[A-Z]\.\s?){1,2}[A-Z][a-z]{2,}"),
)
_TITLED = re.compile(rf"(?<!\w)(?:{_TITLES})\s+({_CAPS})")
_HAN_NAME = re.compile(rf"[{_HAN_SURNAMES}][一-鿿]{{0,2}}?(?={_HAN_ADDRESS})")

# Capitalised words that start a sentence or are titles, never the name itself. Not "Tan" or "Toh":
# both are surnames as well as part of a title.
_NOT_NAME_WORDS = frozenset({
    'tell', 'ask', 'please', 'dear', 'hi', 'hello', 'thanks', 'thank', 'send', 'email', 'call', 'cc', 'to',
    'from', 'and', 'or', 'the', 'with', 'for', 'remind', 'inform', 'reply', 'sila', 'tolong', 'kepada',
    'daripada', 'dan', 'untuk', 'encik', 'en.', 'cik', 'puan', 'pn.', 'tuan', 'tn.', 'haji', 'hj', 'hj.',
    'hajah', 'hjh', 'hjh.', 'dato', "dato'", 'dato’', 'datuk', 'datin', 'sri', 'seri', 'tun', 'dr', 'dr.',
    'prof', 'prof.', 'ir', 'ir.', 'ts', 'ts.', 'ustaz', 'ustazah', 'cikgu', 'mr', 'mr.', 'mrs', 'mrs.', 'ms',
    'ms.', 'mdm', 'mdm.', 'madam', 'miss', 'sir', 'contact', 'forward', 'notify', 'invite', 'meet', 'pay',
    'bcc', 'update', 'let', 'attention', 'attn', 'attn.', 'hubungi', 'maklumkan', 'beritahu', 'jemput', 'minta',
})


def _trimmed(span: str) -> str:
    """The span without leading sentence words or titles ("Tell Datuk Siti binti Ali" -> "Siti binti Ali")."""
    words = span.split()
    while words and words[0].lower() in _NOT_NAME_WORDS:
        words = words[1:]
    return " ".join(words)


def find_name_patterns(text: str) -> list[str]:
    """Every Malaysian-shaped name in the text, as written; titles before a name are left out."""
    found = [match.group(0) for pattern in _PATTERNS for match in pattern.finditer(text)]
    found += [match.group(1) for match in _TITLED.finditer(text)]
    found += [match.group(0) for match in _HAN_NAME.finditer(text)]
    return [name for name in map(_trimmed, found) if name]
