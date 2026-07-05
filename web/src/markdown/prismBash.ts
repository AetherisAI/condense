import { Prism } from 'prism-react-renderer'
import type { Grammar } from 'prismjs'

/**
 * `prism-react-renderer`'s bundled grammar set (D47) covers yaml/json/python/typescript/tsx/
 * sql out of the box but — surprisingly — not bash/shell. Pulling in a whole second Prism
 * instance (or the full `prismjs` package) just for one language would cost MORE than it's
 * worth: `Highlight`'s escape-hatch `prism` prop doesn't replace prism-react-renderer's own
 * vendored default bundle, it sits ALONGSIDE it (that bundle is always included, referenced or
 * not) — confirmed by measurement, adding the real `prismjs` package + a custom instance grew
 * the main chunk instead of shrinking it. So: register a small hand-written grammar directly
 * onto the vendored `Prism` singleton instead. Covers the token classes that matter for
 * readability (comments, strings, `$VARS`, common keywords/builtins, flags) — not Prism's
 * official `prism-bash` (bigger, pulls in more shared grammars), good enough for chat-rendered
 * shell snippets, never used for anything security-sensitive. Registered once at module load;
 * importing this file for its side effect is the whole API.
 */
const bashGrammar: Grammar = {
  comment: /#.*/,
  string: [
    { pattern: /"(?:\\.|\$\([^)]*\)|[^"\\])*"/, greedy: true },
    { pattern: /'[^']*'/, greedy: true },
  ],
  variable: [{ pattern: /\$\{[^}]*\}/, greedy: true }, /\$[\w#@*?$!-]+/],
  keyword:
    /\b(?:if|then|else|elif|fi|for|while|until|do|done|case|esac|function|in|select|time|return|exit|export|local|readonly|declare|set|unset|shift|trap)\b/,
  builtin:
    /\b(?:cd|ls|pwd|echo|printf|grep|egrep|awk|sed|cat|tail|head|find|xargs|npm|npx|git|docker|docker-compose|systemctl|journalctl|pip|python|python3|curl|wget|mkdir|rm|rmdir|cp|mv|touch|chmod|chown|sudo|apt|apt-get|brew|source|test|kill|ps|tar|ssh|scp)\b/,
  flag: /\s-{1,2}[a-zA-Z][\w-]*/,
  number: /\b\d+\b/,
  operator: /&&|\|\||[|&;]|[<>]=?|=/,
  punctuation: /[{}[\]();,.:]/,
}

Prism.languages.bash = bashGrammar
Prism.languages.shell = bashGrammar
Prism.languages.sh = bashGrammar
Prism.languages.shellscript = bashGrammar
