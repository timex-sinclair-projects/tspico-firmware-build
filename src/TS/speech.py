# Speech: English text to SP0256-AL2 allophone numbers
# (docs/v3-speech-proposal.md). The v3 card's chip (tsbus, sp0256.c) speaks
# the numbers; this is the part that runs on core 0, in a command.
#
# 1. Numbers become words.
# 2. Words become NRL phonemes by the letter-to-sound rules (TS/speech_rules,
#    NRL Report 7948 as John A. Wasser coded it, public domain), with his
#    matcher. Words the rules get wrong come from EXCEPTIONS, and from
#    /speech.txt on the Pico's flash (load_exceptions).
# 3. Phonemes become allophones by context, as the AL2 datasheet describes.
#
# Text in square brackets is allophone names, taken as they are:
# "HELLO [PA4] WORLD", "[HH1 EH LL OW]".

from TS.speech_rules import RULES

# The AL2's 64 allophones, by number.
NAMES = ("PA1", "PA2", "PA3", "PA4", "PA5", "OY", "AY", "EH", "KK3", "PP", "JH", "NN1", "IH", "TT2",
         "RR1", "AX", "MM", "TT1", "DH1", "IY", "EY", "DD1", "UW1", "AO", "AA", "YY2", "AE", "HH1",
         "BB1", "TH", "UH", "UW2", "AW", "DD2", "GG3", "VV", "GG1", "SH", "ZH", "RR2", "FF", "KK2",
         "KK1", "ZZ", "NG", "LL", "WW", "XR", "WH", "YY1", "CH", "ER1", "ER2", "OW", "DH2", "SS",
         "NN2", "HH2", "OR", "AR", "YR", "GG2", "EL", "BB2")
NUMBER = {n: i for i, n in enumerate(NAMES)}
PA2, PA4, PA5 = 1, 3, 4

# Words the rules get wrong (about one in ten in ordinary text, by the NRL
# report's own count), as NRL phonemes. /speech.txt adds to these.
EXCEPTIONS = {
    "BROWN": "brAWn", "DOWN": "dAWn", "TOWN": "tAWn", "HUNDRED": "hAHndrIHd",
    "TIMEX": "tAYmEHks", "SINCLAIR": "sIHnklEHr", "THOUSAND": "THAWzAXnd",
    "ONE": "wAHn", "TWO": "tUW", "OF": "AHv", "THE": "DHAX", "TO": "tUW",
    "COMPUTER": "kAXmpyUWtER", "TAPE": "tEYp", "DATA": "dEYtAX",
    "TS": "tIYEHs", "PICO": "pIYkOW", "WANT": "wAAnt", "ERROR": "EHrER", "HI": "hAY",
}


def load_exceptions(path="/speech.txt"):
    """Lines "WORD = phonemes" (NRL phonemes, as in EXCEPTIONS) add to or
    replace the built-in words. Blank lines and lines starting # are
    skipped. Returns how many were read; a missing file is 0."""
    n = 0
    try:
        f = open(path)
    except OSError:
        return 0
    with f:
        for line in f:
            line = line.strip()
            if not line or line[0] == "#" or "=" not in line:
                continue
            w, p = line.split("=", 1)
            w, p = w.strip().upper(), p.strip()
            if w and p:
                EXCEPTIONS[w] = p
                n += 1
    return n


# ---------------------------------------------------------------- the rules
def _vowel(c):
    return c in "AEIOU"


def _cons(c):
    return "A" <= c <= "Z" and c not in "AEIOU"


def _left(pat, w, t):
    """Wasser's leftmatch: the pattern read right to left from w[t] leftwards."""
    for k in range(len(pat) - 1, -1, -1):
        p = pat[k]
        if p == "#":
            if t < 0 or not _vowel(w[t]):
                return False
            t -= 1
            while t >= 0 and _vowel(w[t]):
                t -= 1
        elif p == ":":
            while t >= 0 and _cons(w[t]):
                t -= 1
        elif p == "^":
            if t < 0 or not _cons(w[t]):
                return False
            t -= 1
        elif p == ".":
            if t < 0 or w[t] not in "BDVGJLMNRWZ":
                return False
            t -= 1
        elif p == "+":
            if t < 0 or w[t] not in "EIY":
                return False
            t -= 1
        else:
            if t < 0 or w[t] != p:
                return False
            t -= 1
    return True


def _right(pat, w, t):
    n = len(w)
    for p in pat:
        if p == "#":
            if t >= n or not _vowel(w[t]):
                return False
            t += 1
            while t < n and _vowel(w[t]):
                t += 1
        elif p == ":":
            while t < n and _cons(w[t]):
                t += 1
        elif p == "^":
            if t >= n or not _cons(w[t]):
                return False
            t += 1
        elif p == ".":
            if t >= n or w[t] not in "BDVGJLMNRWZ":
                return False
            t += 1
        elif p == "+":
            if t >= n or w[t] not in "EIY":
                return False
            t += 1
        elif p == "%":                       # ER, E, ES, ED, ING, ELY
            if w.startswith("ING", t):
                t += 3
            elif t < n and w[t] == "E":
                t += 1
                if t < n and w[t] == "R":
                    t += 1
                elif w.startswith("LY", t):
                    t += 2
                elif t < n and w[t] in "SD":
                    t += 1
            else:
                return False
        else:
            if t >= n or w[t] != p:
                return False
            t += 1
    return True


def word_phonemes(word):
    """A word (upper case letters and apostrophes) to NRL phoneme text."""
    if word in EXCEPTIONS:
        return EXCEPTIONS[word]
    w = " " + word + " "
    i = 1
    out = []
    while i < len(w) - 1:
        c = w[i]
        table = RULES.get(c, ()) if "A" <= c <= "Z" else RULES.get("", ())
        for left, match, right, ph in table:
            if w.startswith(match, i) and _left(left, w, i - 1) and _right(right, w, i + len(match)):
                out.append(ph)
                i += len(match)
                break
        else:
            i += 1
    return "".join(out)


def phonemes(text):
    """NRL phoneme text to a list: upper case codes are two letters, lower
    case one; spaces dropped."""
    out = []
    i = 0
    while i < len(text):
        c = text[i]
        if c == " ":
            i += 1
        elif "A" <= c <= "Z":
            out.append(text[i:i + 2])
            i += 2
        else:
            out.append(c)
            i += 1
    return out


# ---------------------------------------------------------------- numbers
_ONES = ("zero one two three four five six seven eight nine ten eleven twelve thirteen "
         "fourteen fifteen sixteen seventeen eighteen nineteen").split()
_TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def say_number(n):
    if n < 20:
        return _ONES[n]
    if n < 100:
        return _TENS[n // 10] + ("" if n % 10 == 0 else " " + _ONES[n % 10])
    if n < 1000:
        return _ONES[n // 100] + " hundred" + ("" if n % 100 == 0 else " and " + say_number(n % 100))
    if n < 1000000:
        r = n % 1000
        return say_number(n // 1000) + " thousand" + ("" if r == 0 else (" and " if r < 100 else " ") + say_number(r))
    return " ".join(_ONES[int(d)] for d in str(n))


# ---------------------------------------------------------------- allophones
_FRONT = ("IY", "IH", "EY", "EH", "AE", "YR", "XR")
_VOWELS = ("IY", "IH", "EY", "EH", "AE", "AA", "AO", "OW", "UH", "UW", "ER", "AX", "AH", "AY", "AW", "OY",
           "AR", "OR", "XR", "YR")
_SIMPLE = {"IY": "IY", "IH": "IH", "EY": "EY", "EH": "EH", "AE": "AE", "AA": "AA", "AO": "AO", "OW": "OW",
           "UH": "UH", "AX": "AX", "AH": "AX", "AY": "AY", "AW": "AW", "OY": "OY",
           "f": "FF", "v": "VV", "TH": "TH", "s": "SS", "z": "ZZ", "SH": "SH", "ZH": "ZH",
           "m": "MM", "NG": "NG", "w": "WW", "CH": "CH", "j": "JH", "WH": "WH", "p": "PP"}
_RCOL = {"AA": "AR", "AO": "OR", "OW": "OR", "UW": "OR", "UH": "OR",
         "EH": "XR", "EY": "XR", "AE": "XR", "IH": "YR", "IY": "YR"}
_VOICED_STOPS = ("BB1", "BB2", "DD1", "DD2", "GG1", "GG2", "GG3", "JH")


def word_allophones(ph):
    """One word's NRL phonemes to AL2 allophone names, each chosen by its
    context as the datasheet describes."""
    m = []
    i = 0
    while i < len(ph):                       # r-coloured vowels; NG before K or G
        a = ph[i]
        b = ph[i + 1] if i + 1 < len(ph) else None
        if b == "r" and a in _RCOL:
            m.append(_RCOL[a])
            i += 2
            continue
        if a == "n" and b in ("k", "g"):
            m.append("NG")
            i += 1
            continue
        m.append(a)
        i += 1
    out = []
    n = len(m)
    for i, p in enumerate(m):
        nxt = m[i + 1] if i + 1 < n else None
        prev = m[i - 1] if i > 0 else None
        initial = i == 0
        final = i == n - 1
        before_vowel = nxt in _VOWELS
        if p in ("AR", "OR", "XR", "YR"):
            a = p
        elif p == "UW":
            a = "UW1" if prev in ("y", "j", "CH", "SH") else "UW2"
        elif p == "ER":
            a = "ER2" if n <= 3 else "ER1"
        elif p in _SIMPLE:
            a = _SIMPLE[p]
        elif p == "t":
            a = "TT2" if (initial or before_vowel) and prev != "s" else "TT1"
        elif p == "d":
            a = "DD2" if initial else "DD1"
        elif p == "b":
            a = "BB2" if initial and before_vowel else "BB1"
        elif p == "k":
            a = "KK2" if (final or not before_vowel) else ("KK1" if nxt in _FRONT else "KK3")
        elif p == "g":
            a = "GG3" if final else ("GG1" if nxt in _FRONT else "GG2")
        elif p == "DH":
            a = "DH1" if initial else "DH2"
        elif p in ("HH", "h"):
            a = "HH1" if nxt in _FRONT else "HH2"
        elif p == "n":
            a = "NN2" if initial else "NN1"
        elif p == "l":
            a = "EL" if final and prev not in _VOWELS else "LL"
        elif p == "y":
            a = "YY1" if nxt == "UW" else "YY2"
        elif p == "r":
            a = "RR1" if initial else "RR2"
        else:
            continue
        # A short pause before a voiced stop released into a vowel, inside a
        # word, as the datasheet's examples do.
        if a in _VOICED_STOPS and out and before_vowel:
            out.append("PA1")
        out.append(a)
    return out


def _words(text):
    """Text to tokens: words (upper case letters and apostrophes), numbers,
    the punctuation that pauses (. , ! ? ;), and [allophones] as one token."""
    out = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c == "[":
            j = text.find("]", i)
            j = n if j < 0 else j
            out.append(text[i:j + 1])
            i = j + 1
        elif c.isalpha() or c == "'":
            j = i
            while j < n and (text[j].isalpha() or text[j] == "'"):
                j += 1
            out.append(text[i:j].upper())
            i = j
        elif c.isdigit():
            j = i
            while j < n and text[j].isdigit():
                j += 1
            out += [w.upper() for w in say_number(int(text[i:j])).split()]
            i = j
        else:
            if c in ".,!?;":
                out.append(c)
            i += 1
    return out


def allophones(text):
    """Text to AL2 allophone numbers, a bytearray, ending in a pause. A name
    in [brackets] that isn't an allophone raises ValueError."""
    out = bytearray()
    for tok in _words(text):
        if tok[0] == "[":
            for name in tok[1:-1].replace(",", " ").split():
                name = name.upper()
                if name not in NUMBER:
                    raise ValueError(name)
                out.append(NUMBER[name])
            continue
        if tok in ".!?;":
            out.append(PA5)
            continue
        if tok == ",":
            out.append(PA4)
            continue
        if out and out[-1] not in (PA4, PA5):
            out.append(PA2)
        for a in word_allophones(phonemes(word_phonemes(tok))):
            out.append(NUMBER[a])
    if not out or out[-1] != PA5:
        out.append(PA5)
    return out
