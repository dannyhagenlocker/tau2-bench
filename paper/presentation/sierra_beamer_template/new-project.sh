#!/bin/bash
# =============================================================================
# Sierra Beamer Template - New Project Script
# =============================================================================
# Creates a new presentation project with all necessary files.
#
# Usage: ./new-project.sh <project-name> [destination-path]
#
# Examples:
#   ./new-project.sh my-presentation
#   ./new-project.sh quarterly-review ~/Documents/presentations
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

CHECK="✓"
ARROW="→"

# Get the directory where this script lives (template root)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Parse arguments
PROJECT_NAME="${1:-}"
DEST_PATH="${2:-.}"

# Show usage if no project name
if [[ -z "$PROJECT_NAME" ]]; then
    echo ""
    echo -e "${BLUE}Sierra Beamer - Create New Presentation${NC}"
    echo ""
    echo "Usage: $0 <project-name> [destination-path]"
    echo ""
    echo "Examples:"
    echo "  $0 my-presentation"
    echo "  $0 quarterly-review ~/Documents/presentations"
    echo ""
    exit 1
fi

# Clean project name (remove spaces, special chars)
CLEAN_NAME=$(echo "$PROJECT_NAME" | tr ' ' '-' | tr -cd '[:alnum:]-_')

# Determine full project path
if [[ "$DEST_PATH" == "." ]]; then
    PROJECT_PATH="$(pwd)/$CLEAN_NAME"
else
    PROJECT_PATH="$DEST_PATH/$CLEAN_NAME"
fi

echo ""
echo -e "${BLUE}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║        Sierra Beamer - Creating New Presentation              ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${ARROW} Project name: ${YELLOW}$CLEAN_NAME${NC}"
echo -e "${ARROW} Location: ${YELLOW}$PROJECT_PATH${NC}"
echo ""

# Check if directory already exists
if [[ -d "$PROJECT_PATH" ]]; then
    echo -e "${RED}Error: Directory already exists: $PROJECT_PATH${NC}"
    echo "Please choose a different name or delete the existing directory."
    exit 1
fi

# Create project directory
mkdir -p "$PROJECT_PATH"

# Copy template files
echo -e "${ARROW} Copying template files..."

# Copy style files
cp "$SCRIPT_DIR"/*.sty "$PROJECT_PATH/"

# Copy fonts
mkdir -p "$PROJECT_PATH/fonts"
cp "$SCRIPT_DIR/fonts/"*.otf "$PROJECT_PATH/fonts/"
cp "$SCRIPT_DIR/fonts/LICENSE.txt" "$PROJECT_PATH/fonts/"

# Copy assets
mkdir -p "$PROJECT_PATH/assets"
cp "$SCRIPT_DIR/assets/"* "$PROJECT_PATH/assets/"

# Copy Cursor rules if they exist
if [[ -d "$SCRIPT_DIR/.cursor" ]]; then
    cp -r "$SCRIPT_DIR/.cursor" "$PROJECT_PATH/"
fi

# Copy .cursorignore if it exists
if [[ -f "$SCRIPT_DIR/.cursorignore" ]]; then
    cp "$SCRIPT_DIR/.cursorignore" "$PROJECT_PATH/"
fi

echo -e "${GREEN}${CHECK} Template files copied${NC}"

# Create the main presentation file
echo -e "${ARROW} Creating main presentation file..."

cat > "$PROJECT_PATH/$CLEAN_NAME.tex" << 'LATEX_TEMPLATE'
%% =============================================================================
%% PROJECT_TITLE - Sierra Presentation
%% =============================================================================
%% Created with Sierra Beamer Template
%% Build with: xelatex PROJECT_NAME.tex
%% =============================================================================

\documentclass[aspectratio=169]{beamer}

%% Load Sierra theme
%% Options: [dark] for dark mode, [minimal] for no footer, [notitlebackground] for light title
\usetheme[notitlebackground]{Sierra}

%% Additional packages (add more as needed)
\usepackage{booktabs}  % Better tables

%% =============================================================================
%% Presentation Metadata - EDIT THESE
%% =============================================================================

\title{Your Presentation Title}
\author{Your Name}
\institute{your.email@sierra.ai}
\date{}

%% Sierra logo for title page (bottom-right corner)
\newcommand{\sierralogo}{%
  \includegraphics[height=1.2cm]{assets/sierra-logo-white.png}%
}

%% =============================================================================
%% Document
%% =============================================================================

\begin{document}

%% -----------------------------------------------------------------------------
%% Title Slide
%% -----------------------------------------------------------------------------

{
\usebackgroundtemplate{%
  \includegraphics[width=\paperwidth,height=\paperheight]{assets/sierra-forest-bg.png}%
}
\begin{frame}[plain]
  \titlepage
\end{frame}
}

%% -----------------------------------------------------------------------------
%% Agenda / Overview
%% -----------------------------------------------------------------------------

\begin{frame}{Agenda}
  
  \begin{enumerate}
    \item First topic
    \item Second topic
    \item Third topic
    \item Summary
  \end{enumerate}
  
\end{frame}

%% -----------------------------------------------------------------------------
%% Content Slides - Add your slides here
%% -----------------------------------------------------------------------------

\begin{frame}{Slide Title}
  
  Your content goes here.
  
  \begin{itemize}
    \item First point
    \item Second point
    \item Third point
  \end{itemize}
  
\end{frame}

%% -----------------------------------------------------------------------------
%% Thank You Slide
%% -----------------------------------------------------------------------------

{
\usebackgroundtemplate{%
  \includegraphics[width=\paperwidth,height=\paperheight]{assets/sierra-dusk-bg.jpg}%
}
\begin{frame}[plain]
  \centering
  \vfill
  {\fontsize{48}{58}\selectfont\interlight\textcolor{SierraWhite}{Thank you{\large\textbullet}}}
  \vspace{2.5em}
  \includegraphics[height=1.5cm]{assets/sierra-logo-white.png}
  \vfill
\end{frame}
}

\end{document}
LATEX_TEMPLATE

# Replace placeholders
sed -i.bak "s/PROJECT_TITLE/$CLEAN_NAME/g" "$PROJECT_PATH/$CLEAN_NAME.tex"
sed -i.bak "s/PROJECT_NAME/$CLEAN_NAME/g" "$PROJECT_PATH/$CLEAN_NAME.tex"
rm -f "$PROJECT_PATH/$CLEAN_NAME.tex.bak"

echo -e "${GREEN}${CHECK} Main presentation file created: $CLEAN_NAME.tex${NC}"

# Create project Makefile
echo -e "${ARROW} Creating Makefile..."

cat > "$PROJECT_PATH/Makefile" << MAKEFILE
# Sierra Presentation Makefile
# Usage: make build

LATEX = xelatex
LATEXFLAGS = -interaction=nonstopmode
MAIN = $CLEAN_NAME

.PHONY: build clean watch open help

help:
	@echo "Sierra Presentation - Build Commands"
	@echo ""
	@echo "  make build   - Compile the presentation to PDF"
	@echo "  make clean   - Remove auxiliary files"
	@echo "  make open    - Open the PDF (macOS)"
	@echo "  make watch   - Watch for changes and rebuild (requires fswatch)"
	@echo ""

build: \$(MAIN).pdf

\$(MAIN).pdf: \$(MAIN).tex *.sty
	@echo "Building presentation..."
	@\$(LATEX) \$(LATEXFLAGS) \$(MAIN).tex > /dev/null
	@\$(LATEX) \$(LATEXFLAGS) \$(MAIN).tex > /dev/null
	@echo "Done! Output: \$(MAIN).pdf"

clean:
	@rm -f *.aux *.log *.nav *.out *.snm *.toc *.vrb *.fls *.fdb_latexmk *.synctex.gz
	@echo "Cleaned auxiliary files."

open: build
	@open \$(MAIN).pdf 2>/dev/null || xdg-open \$(MAIN).pdf 2>/dev/null || echo "Please open \$(MAIN).pdf manually"

watch:
	@echo "Watching for changes... (Ctrl+C to stop)"
	@fswatch -o \$(MAIN).tex *.sty | xargs -n1 -I{} make build
MAKEFILE

echo -e "${GREEN}${CHECK} Makefile created${NC}"

# Create .gitignore
echo -e "${ARROW} Creating .gitignore..."

cat > "$PROJECT_PATH/.gitignore" << 'GITIGNORE'
# LaTeX auxiliary files
*.aux
*.log
*.nav
*.out
*.snm
*.toc
*.vrb
*.fls
*.fdb_latexmk
*.synctex.gz
*.bbl
*.blg

# OS files
.DS_Store
Thumbs.db

# Editor files
*.swp
*.swo
*~

# Keep the PDF
!*.pdf
GITIGNORE

echo -e "${GREEN}${CHECK} .gitignore created${NC}"

# Create a simple README for the project
cat > "$PROJECT_PATH/README.md" << README
# $CLEAN_NAME

A Sierra presentation created with [Sierra Beamer Template](https://github.com/sierra-ai/sierra-beamer-template).

## Building

\`\`\`bash
make build
\`\`\`

Or directly with:

\`\`\`bash
xelatex $CLEAN_NAME.tex
\`\`\`

## Editing with Cursor

Open this folder in Cursor and use the AI to help you create slides:

- Ask: "Add a slide about [topic]"
- Ask: "Create a two-column comparison slide"
- Ask: "Add a quote slide with [quote]"

The \`.cursor/rules\` file helps the AI understand the Sierra template format.

## Files

- \`$CLEAN_NAME.tex\` - Main presentation file (edit this)
- \`assets/\` - Background images and logos
- \`fonts/\` - Inter font family
- \`*.sty\` - Sierra theme files (don't edit)
README

echo -e "${GREEN}${CHECK} README created${NC}"

# Final success message
echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              Presentation Created Successfully! 🎉            ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "Your new presentation is ready at:"
echo -e "  ${YELLOW}$PROJECT_PATH${NC}"
echo ""
echo -e "Next steps:"
echo -e "  ${ARROW} Open in Cursor:  ${YELLOW}cursor $PROJECT_PATH${NC}"
echo -e "  ${ARROW} Build PDF:       ${YELLOW}cd $PROJECT_PATH && make build${NC}"
echo -e "  ${ARROW} Open PDF:        ${YELLOW}cd $PROJECT_PATH && make open${NC}"
echo ""
echo -e "Start editing ${YELLOW}$CLEAN_NAME.tex${NC} to create your slides!"
echo ""


