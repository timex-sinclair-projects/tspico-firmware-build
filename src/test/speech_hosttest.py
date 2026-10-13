#!/usr/bin/env python3
"""Speech text to allophones (src/TS/speech.py), on the host.

The two sentences sp0256_hosttest.py speaks come from here: the same
allophone numbers. Then the parts: the rules on words they get right and
wrong, numbers, the exception list and /speech.txt, [allophones] in text,
and the pauses punctuation makes.

Run:  python3 src/test/speech_hosttest.py
"""

import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from TS import speech  # noqa: E402

FAILS = []


def check(ok, what):
    print(("  ok   " if ok else "  FAIL ") + what)
    if not ok:
        FAILS.append(what)


def names(text):
    return " ".join(speech.NAMES[i] for i in speech.allophones(text))


def main():
    print("the rules")
    n = sum(len(v) for v in speech.RULES.values())
    check(n == 354, "354 rules from english.c (%d)" % n)
    check(len(speech.NAMES) == 64 and speech.NUMBER["PA5"] == 4 and speech.NUMBER["BB2"] == 63,
          "the AL2's 64 allophones, numbered as on the chip")

    print("sentences (sp0256_hosttest.py speaks these numbers)")
    check(list(speech.allophones("Hello. I am your Timex Sinclair two thousand and sixty eight.")) ==
          [27, 7, 45, 53, 4, 6, 1, 26, 16, 1, 25, 58, 1, 13, 6, 16, 7, 41, 55, 1, 55, 12, 44, 41, 45, 47, 1, 13,
           31, 1, 29, 32, 43, 15, 11, 21, 1, 26, 11, 21, 1, 55, 12, 41, 55, 17, 19, 1, 20, 17, 4],
          "Hello. I am your Timex Sinclair two thousand and sixty eight.")
    check(list(speech.allophones("Press any key to continue.")) ==
          [9, 39, 7, 55, 1, 7, 11, 19, 1, 42, 19, 1, 13, 31, 1, 8, 24, 11, 13, 12, 11, 49, 22, 4],
          "Press any key to continue.")

    print("allophones by context")
    for text, want in (("cat", "KK1 AE TT1 PA2"),          # K before a front vowel
                       ("cool", "KK3 UW2 LL PA2"),         # ... before a back vowel
                       ("back", "BB2 AE KK2 PA2"),         # final K
                       ("game", "GG1 EY MM PA2"),
                       ("dog", "DD2 AA GG3 PA2"),          # the rules' American "o"
                       ("car", "KK3 AR PA2"),              # r-coloured vowels
                       ("sink", "SS IH NG KK2 PA2"),       # N before K
                       ("the", "DH1 AX PA2")):
        check(names(text) == want, "%-5s -> %s (%s)" % (text, want, names(text)))

    print("numbers")
    check(speech.say_number(2068) == "two thousand and sixty eight", "2068: two thousand and sixty eight")
    check(speech.say_number(1983) == "one thousand nine hundred and eighty three", "1983")
    check(speech.say_number(100) == "one hundred" and speech.say_number(42) == "forty two", "100, 42")
    check(speech.say_number(1234567) == "one two three four five six seven", "past a million: digits")
    check(speech.allophones("2068") == speech.allophones("two thousand and sixty eight"), "digits in text are spoken")

    print("exceptions")
    check(names("brown") == "BB1 RR2 AW NN1 PA2", "BROWN from the list, not the rules (%s)" % names("brown"))
    d = tempfile.mkdtemp()
    try:
        p = os.path.join(d, "speech.txt")
        with open(p, "w") as f:
            f.write("# my words\nzebra = zIYbrAX\n\nnot a rule line\nPICO = pAYkOW\n")
        saved = dict(speech.EXCEPTIONS)
        got = speech.load_exceptions(p)
        check(got == 2 and speech.word_phonemes("ZEBRA") == "zIYbrAX" and speech.word_phonemes("PICO") == "pAYkOW",
              "/speech.txt adds words and replaces built-in ones (%d read)" % got)
        speech.EXCEPTIONS.clear()
        speech.EXCEPTIONS.update(saved)
        check(speech.load_exceptions(os.path.join(d, "none.txt")) == 0, "no /speech.txt: nothing read, no error")
    finally:
        for f in os.listdir(d):
            os.remove(os.path.join(d, f))
        os.rmdir(d)

    print("[allophones] in text")
    check(names("[HH1 EH LL OW]") == "HH1 EH LL OW PA2", "names taken as they are; a word gap added")
    check(names("[hh1, eh, ll, ow, pa5]") == "HH1 EH LL OW PA5", "lower case and commas")
    check(names("hi [PA4] there").split()[:6] == ["HH2", "AY", "PA4", "DH1", "XR", "PA2"],
          "mixed with words (%s)" % names("hi [PA4] there"))
    try:
        speech.allophones("[HH1 XYZ]")
        raised = False
    except ValueError:
        raised = True
    check(raised, "an unknown allophone name is ValueError")

    print("pauses")
    check(names("yes, no") == "YY2 EH SS PA4 NN2 OW PA2", "a comma: PA4 (%s)" % names("yes, no"))
    check(names("yes. no!") == "YY2 EH SS PA5 NN2 OW PA5", "a full stop and !: PA5")
    check(names("yes;") == "YY2 EH SS PA5" and names("yes?") == "YY2 EH SS PA5", "; and ?: PA5")
    check(names("yes,") == "YY2 EH SS PA4", "ending in a comma: PA4, nothing more")
    check(names("") == "PA5", "nothing to say: one pause")

    print("text in pieces")
    # tpi:say holds 23 characters, so a long sentence goes in pieces. A piece
    # ending in a word gets only the gap between words, so the pieces join
    # as the whole sentence does; the end of a sentence still pauses.
    whole = "Press any key to continue."
    check(speech.allophones("Press any key") + speech.allophones("to continue.") == speech.allophones(whole),
          "two pieces say exactly what the whole sentence does")
    check(names("[HH1 EH LL OW PA3]") == "HH1 EH LL OW PA3", "[...] ending in a pause: nothing added")

    print()
    if FAILS:
        print("%d FAILED" % len(FAILS))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
