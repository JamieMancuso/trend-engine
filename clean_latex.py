"""
LaTeX-to-plain-text cleaner for arXiv abstracts.

arXiv stores abstracts with LaTeX markup. For human-readable display,
run abstracts through clean_latex() before rendering.

For LLM consumption, DO NOT clean — pass raw LaTeX. Modern LLMs parse
LaTeX natively and the markup carries semantic meaning (e.g., \\mathbb{R}
vs R) that the cleaner strips.

Usage:
    from clean_latex import clean_latex
    readable = clean_latex(raw_abstract)

Coverage: handles ~95% of common arXiv abstract markup. Edge cases
(matrix environments, multi-line equations, custom macros) may leave
artifacts.
"""

import re

# Greek letters (lowercase)
GREEK_LOWER = {
    r'\\alpha': 'α', r'\\beta': 'β', r'\\gamma': 'γ', r'\\delta': 'δ',
    r'\\epsilon': 'ε', r'\\varepsilon': 'ε', r'\\zeta': 'ζ', r'\\eta': 'η',
    r'\\theta': 'θ', r'\\vartheta': 'ϑ', r'\\iota': 'ι', r'\\kappa': 'κ',
    r'\\lambda': 'λ', r'\\mu': 'μ', r'\\nu': 'ν', r'\\xi': 'ξ',
    r'\\pi': 'π', r'\\rho': 'ρ', r'\\sigma': 'σ', r'\\tau': 'τ',
    r'\\upsilon': 'υ', r'\\phi': 'φ', r'\\varphi': 'φ', r'\\chi': 'χ',
    r'\\psi': 'ψ', r'\\omega': 'ω',
}
# Greek letters (uppercase)
GREEK_UPPER = {
    r'\\Gamma': 'Γ', r'\\Delta': 'Δ', r'\\Theta': 'Θ', r'\\Lambda': 'Λ',
    r'\\Xi': 'Ξ', r'\\Pi': 'Π', r'\\Sigma': 'Σ', r'\\Phi': 'Φ',
    r'\\Psi': 'Ψ', r'\\Omega': 'Ω',
}
# Mathematical operators and relations
OPS = {
    r'\\sum': '∑', r'\\prod': '∏', r'\\int': '∫',
    r'\\leq': '≤', r'\\geq': '≥', r'\\neq': '≠',
    r'\\approx': '≈', r'\\sim': '~', r'\\equiv': '≡',
    r'\\pm': '±', r'\\mp': '∓', r'\\times': '×', r'\\cdot': '·',
    r'\\in': '∈', r'\\notin': '∉', r'\\subset': '⊂', r'\\subseteq': '⊆',
    r'\\cup': '∪', r'\\cap': '∩', r'\\infty': '∞',
    r'\\rightarrow': '→', r'\\to': '→', r'\\leftarrow': '←',
    r'\\Rightarrow': '⇒', r'\\Leftarrow': '⇐',
    r'\\partial': '∂', r'\\nabla': '∇', r'\\forall': '∀', r'\\exists': '∃',
    r'\\ldots': '...', r'\\dots': '...', r'\\cdots': '...',
}
# Blackboard bold (number sets)
BLACKBOARD = {
    r'\\mathbb\{R\}': 'ℝ', r'\\mathbb\{N\}': 'ℕ', r'\\mathbb\{Z\}': 'ℤ',
    r'\\mathbb\{Q\}': 'ℚ', r'\\mathbb\{C\}': 'ℂ', r'\\mathbb\{E\}': '𝔼',
}


def clean_latex(s):
    """Convert LaTeX markup to readable plain text with Unicode math symbols."""
    if not isinstance(s, str):
        return s

    # Norms: \lVert ... \rVert → ||...||
    s = re.sub(r'\\lVert\s*', '||', s)
    s = re.sub(r'\\rVert', '||', s)
    s = re.sub(r'\\Vert', '||', s)
    s = re.sub(r'\\\|', '||', s)

    # Fractions: \frac{a}{b} → (a)/(b)
    s = re.sub(r'\\frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}', r'(\1)/(\2)', s)

    # Greek letters (word-boundary guard prevents \alpha matching \alphabet)
    for pat, rep in {**GREEK_UPPER, **GREEK_LOWER}.items():
        s = re.sub(pat + r'(?![a-zA-Z])', rep, s)

    # Operators / relations
    for pat, rep in OPS.items():
        s = re.sub(pat + r'(?![a-zA-Z])', rep, s)

    # Blackboard bold
    for pat, rep in BLACKBOARD.items():
        s = re.sub(pat, rep, s)

    # Text styling: \textbf{x} → **x**, others → x
    s = re.sub(r'\\textbf\{([^{}]*)\}', r'**\1**', s)
    s = re.sub(r'\\textit\{([^{}]*)\}', r'\1', s)
    s = re.sub(r'\\emph\{([^{}]*)\}', r'\1', s)
    s = re.sub(r'\\text\{([^{}]*)\}', r'\1', s)
    s = re.sub(r'\\mathcal\{([^{}]*)\}', r'\1', s)
    s = re.sub(r'\\mathbf\{([^{}]*)\}', r'\1', s)
    s = re.sub(r'\\mathrm\{([^{}]*)\}', r'\1', s)

    # Strip math delimiters
    s = s.replace('$$', '').replace('$', '')

    # Collapse \left( \right) sizing macros
    s = re.sub(r'\\left\s*', '', s)
    s = re.sub(r'\\right\s*', '', s)

    # Thin-space macros → regular space
    s = re.sub(r'\\[,;!]', ' ', s)
    s = re.sub(r'\\quad\b', '  ', s)
    s = re.sub(r'\\qquad\b', '    ', s)

    # Any remaining \macroname → strip the backslash
    s = re.sub(r'\\([a-zA-Z]+)', r'\1', s)

    # Collapse whitespace
    s = re.sub(r'\s+', ' ', s).strip()
    return s


if __name__ == '__main__':
    # Self-test
    test = r"weighted sum $\sum_{i=1}^N \alpha_i k(x,x_i)$ to precision $\varepsilon$, with $\lVert\alpha\rVert_1/\varepsilon$"
    print("IN :", test)
    print("OUT:", clean_latex(test))
