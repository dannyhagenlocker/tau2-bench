# Sierra Beamer Template Makefile
# Usage: make example

LATEX = xelatex
LATEXFLAGS = -interaction=nonstopmode

.PHONY: all example clean install help

help:
	@echo "Sierra Beamer Template"
	@echo ""
	@echo "Usage:"
	@echo "  make example    - Compile the example presentation"
	@echo "  make clean      - Remove auxiliary files"
	@echo "  make install    - Install theme to ~/texmf"
	@echo ""

example: examples/example-presentation.pdf

examples/example-presentation.pdf: examples/example-presentation.tex *.sty
	@echo "Compiling example presentation..."
	@cp *.sty examples/
	@cd examples && $(LATEX) $(LATEXFLAGS) example-presentation.tex > /dev/null
	@cd examples && $(LATEX) $(LATEXFLAGS) example-presentation.tex > /dev/null
	@cd examples && rm -f *.aux *.log *.nav *.out *.snm *.toc *.sty
	@echo "Done! Output: examples/example-presentation.pdf"

clean:
	@echo "Cleaning auxiliary files..."
	@find . -name "*.aux" -delete
	@find . -name "*.log" -delete
	@find . -name "*.nav" -delete
	@find . -name "*.out" -delete
	@find . -name "*.snm" -delete
	@find . -name "*.toc" -delete
	@find . -name "*.vrb" -delete
	@echo "Done!"

install:
	@echo "Installing to ~/texmf/tex/latex/sierra-beamer..."
	@mkdir -p ~/texmf/tex/latex/sierra-beamer
	@cp *.sty ~/texmf/tex/latex/sierra-beamer/
	@texhash ~/texmf 2>/dev/null || true
	@echo "Done! Theme installed system-wide."

