"""Split a Bash command line into its simple commands — shared by the PreToolUse(Bash) guards.

Not a shell: just enough structure to tell code from data, so a guard neither fires on text
(``grep -rn 'git stash' docs/``, a heredoc body) nor misses code a quote hides
(``OUT="$(git stash)"``, ``bash -lc 'git stash'``).

- Separators (``;`` ``&&`` ``||`` ``|`` ``&`` newline, parentheses) end a command; a redirection is
  dropped with its target and never swallows the separator after it.
- A quoted part of a word is data: its text becomes ``QUOTED`` and ``Word.raw`` keeps the content.
- Command substitution (``$(…)``, backticks, ``<(…)``) is code wherever it stands, inside double
  quotes too: its commands are returned on their own and the word holds ``QUOTED`` in its place.
- A heredoc body and a ``#`` comment are data.
- ``bash -c '…'`` (``-lc``, ``-ic``, any short flags ending in c) and ``eval`` hand a string to a
  shell: the string is split as well.
"""
from __future__ import annotations

import re

QUOTED = "__quoted__"
SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}

_HEREDOC = re.compile(r"<<-?[ \t]*(?:([\"'])(.*?)\1|\\?([\w.-]+))")
_REDIRECT = re.compile(r"&?(?:<<<|<>|>>|>\||<|>)(?:&(?P<fd>\d+|-)?)?")
_ASSIGN = re.compile(r"[A-Za-z_]\w*\+?=")
_AMOUNT = re.compile(r"\d+(?:\.\d+)?[smhd]?")
_SHELL_C = re.compile(r"-[A-Za-z]*c")
# Words that pass the next word through as the command, and their options that take a value.
_WRAPPERS = {"sudo": {"-u", "-g"}, "doas": {"-u"}, "env": {"-u"}, "command": (), "exec": (), "builtin": (),
             "noglob": (), "nohup": (), "time": (), "timeout": {"-s", "-k"}, "nice": {"-n"}, "stdbuf": (),
             "xargs": {"-I", "-J", "-n", "-P", "-L", "-s", "-E", "-d", "-R"},
             "if": (), "then": (), "else": (), "elif": (), "do": (), "while": (), "until": (),
             "!": (), "{": ()}
_EXEC = {"-exec", "-execdir", "-ok", "-okdir"}  # find


class Word(str):
    """One shell word. The text has each quoted part replaced by ``QUOTED`` (data is never a flag);
    ``raw`` is the word with the quotes removed and their content kept."""
    raw = ""


class _Scanner:
    def __init__(self, text: str):
        self.s, self.out, self.heredocs, self.n = text, [], [], 0

    def scope(self, parent: tuple) -> tuple:
        self.n += 1
        return parent + (self.n,)

    def run(self, i: int, scope: tuple, closer: str | None) -> int:
        """Scan commands from ``i`` up to ``closer`` (``)`` or a backtick; None = the end)."""
        s, n = self.s, len(self.s)
        words, text, raw = [], [], []
        in_word = drop = False

        def end_word():
            nonlocal in_word, drop
            if in_word:
                if not drop:
                    w = Word("".join(text))
                    w.raw = "".join(raw)
                    words.append(w)
                drop = False
            del text[:], raw[:]
            in_word = False

        def end_command():
            nonlocal drop
            end_word()
            drop = False
            if words:
                self.out.append((list(words), scope))
                del words[:]

        while i < n:
            c, two = s[i], s[i:i + 2]
            if c == closer:
                end_command()
                return i + 1
            if c == "\\":
                if two != "\\\n":  # a backslash-newline joins two lines
                    text.append(s[i + 1:i + 2])
                    raw.append(s[i + 1:i + 2])
                    in_word = True
                i += 2
            elif c == "'":
                j = s.find("'", i + 1)
                j = n if j < 0 else j
                text.append(QUOTED)
                raw.append(s[i + 1:j])
                in_word = True
                i = j + 1
            elif c == '"':
                text.append(QUOTED)
                in_word = True
                i = self.dquote(i + 1, scope, raw)
            elif two in ("$(", "<(", ">(") or c == "`":
                text.append(QUOTED)
                raw.append(QUOTED)
                in_word = True
                i = self.run(i + (1 if c == "`" else 2), self.scope(scope), "`" if c == "`" else ")")
            elif c in " \t":
                end_word()
                i += 1
            elif c == "#" and not in_word:
                j = s.find("\n", i)
                i = n if j < 0 else j
            elif c == "\n":
                end_command()
                i = self.skip_heredocs(i + 1)
            elif c in "<>" or two == "&>":
                if in_word and "".join(text).isdigit():  # `2>`: the descriptor is not an argument
                    del text[:], raw[:]
                    in_word = False
                else:
                    end_word()
                m = _HEREDOC.match(s, i)
                if m:
                    self.heredocs.append(m.group(2) if m.group(1) else m.group(3))
                    i = m.end()
                else:
                    m = _REDIRECT.match(s, i)
                    i = m.end()
                    drop = m.group("fd") is None  # the next word is the target, not an argument
            elif c in ";|&":
                end_command()
                i += 1
            elif c == "(":
                end_command()
                i = self.run(i + 1, self.scope(scope), ")")
            elif c == ")":
                end_command()
                i += 1
            else:
                text.append(c)
                raw.append(c)
                in_word = True
                i += 1
        end_command()
        return i

    def dquote(self, i: int, scope: tuple, raw: list) -> int:
        """Inside double quotes: text is data, command substitution is code."""
        s, n = self.s, len(self.s)
        while i < n and s[i] != '"':
            c = s[i]
            if c == "\\" and s[i + 1:i + 2] in ("$", "`", '"', "\\", "\n"):
                if s[i + 1] != "\n":
                    raw.append(s[i + 1])
                i += 2
            elif c == "`" or s[i:i + 2] == "$(":
                raw.append(QUOTED)
                i = self.run(i + (1 if c == "`" else 2), self.scope(scope), "`" if c == "`" else ")")
            else:
                raw.append(c)
                i += 1
        return i + 1

    def skip_heredocs(self, i: int) -> int:
        """Past the bodies of the heredocs opened on the line that just ended."""
        s, n = self.s, len(self.s)
        while self.heredocs:
            marker = self.heredocs.pop(0)
            while i < n:
                j = s.find("\n", i)
                j = n if j < 0 else j
                line, i = s[i:j], min(j + 1, n)
                if line.strip() == marker:
                    break
        return i


def name(word: Word) -> str:
    """The program a word names: ``/usr/bin/git`` → ``git``."""
    return word.raw.rsplit("/", 1)[-1]


def command_words(words: list) -> list:
    """Indexes of the words in command position: the first word after ``VAR=value`` prefixes and
    pass-through wrappers (``sudo``, ``env``, ``timeout 5``, ``xargs -r``, ``then`` …), and the
    word after find's ``-exec``. ``grep git`` and ``which git`` name git; they do not run it."""
    out, i = [], 0
    while i < len(words):
        w = words[i]
        if _ASSIGN.match(w):
            i += 1
        elif name(w) in _WRAPPERS:
            with_value = _WRAPPERS[name(w)]
            i += 1
            while i < len(words) and (words[i].startswith("-") or _AMOUNT.fullmatch(words[i]) or words[i] == "{}"):
                i += 2 if words[i] in with_value else 1
        else:
            out.append(i)
            break
    return out + [k + 1 for k, w in enumerate(words[:-1]) if w in _EXEC and k + 1 not in out]


def payloads(words: list) -> list:
    """Strings this command hands to a shell to run."""
    out = []
    for i, w in enumerate(words):
        if name(w) in SHELLS:
            j = next((j for j in range(i + 1, len(words) - 1) if _SHELL_C.fullmatch(words[j])), None)
            if j is not None:
                out.append(words[j + 1].raw)
    for k in command_words(words):
        if name(words[k]) == "eval":
            out.append(" ".join(w.raw for w in words[k + 1:]))
    return out


def commands(command: str, depth: int = 0, scope: tuple = (0,)) -> list:
    """``[(words, scope)]`` in the order the shell starts them, shell payloads included.

    ``scope`` identifies the subshell, substitution or payload a command runs in; its parent is
    ``scope[:-1]``. A ``cd`` holds for the rest of its own scope and the scopes opened inside it."""
    scanner = _Scanner(command)
    scanner.run(0, scope, None)
    out = []
    for words, sc in scanner.out:
        out.append((words, sc))
        if depth < 3:
            for payload in payloads(words):
                out += commands(payload, depth + 1, sc + ("payload%d" % len(out),))
    return out
