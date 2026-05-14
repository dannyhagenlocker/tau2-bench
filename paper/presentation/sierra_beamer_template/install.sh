#!/bin/bash
# =============================================================================
# Sierra Beamer Template - Installation Script
# =============================================================================
# This script installs all dependencies needed to build Sierra presentations.
# Supports macOS (via Homebrew) and Linux (Ubuntu/Debian).
#
# Usage: ./install.sh
# =============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Emoji for visual feedback
CHECK="✓"
CROSS="✗"
ARROW="→"

echo ""
echo -e "${BLUE}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║       Sierra Beamer Template - Installation Script            ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Detect OS
detect_os() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macos"
    elif [[ -f /etc/debian_version ]]; then
        echo "debian"
    elif [[ -f /etc/redhat-release ]]; then
        echo "redhat"
    else
        echo "unknown"
    fi
}

OS=$(detect_os)
echo -e "${ARROW} Detected OS: ${YELLOW}${OS}${NC}"
echo ""

# Check if a command exists
command_exists() {
    command -v "$1" &> /dev/null
}

# Install Homebrew on macOS if needed
install_homebrew() {
    if ! command_exists brew; then
        echo -e "${YELLOW}${ARROW} Installing Homebrew...${NC}"
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        
        # Add Homebrew to PATH for Apple Silicon Macs
        if [[ -f /opt/homebrew/bin/brew ]]; then
            eval "$(/opt/homebrew/bin/brew shellenv)"
        fi
        echo -e "${GREEN}${CHECK} Homebrew installed${NC}"
    else
        echo -e "${GREEN}${CHECK} Homebrew already installed${NC}"
    fi
}

# Install LaTeX on macOS
install_latex_macos() {
    echo ""
    echo -e "${BLUE}Installing LaTeX (BasicTeX + required packages)...${NC}"
    echo -e "${YELLOW}  This may take 5-10 minutes on first install.${NC}"
    echo ""
    
    if command_exists xelatex; then
        echo -e "${GREEN}${CHECK} LaTeX (XeLaTeX) already installed${NC}"
    else
        # Install BasicTeX (smaller than full MacTeX)
        echo -e "${ARROW} Installing BasicTeX via Homebrew..."
        brew install --cask basictex
        
        # Add TeX Live to PATH
        export PATH="/Library/TeX/texbin:$PATH"
        
        # Update tlmgr
        echo -e "${ARROW} Updating TeX Live Manager..."
        sudo tlmgr update --self
        
        echo -e "${GREEN}${CHECK} BasicTeX installed${NC}"
    fi
    
    # Install required LaTeX packages
    echo ""
    echo -e "${ARROW} Installing required LaTeX packages..."
    sudo tlmgr install \
        beamer \
        etoolbox \
        fontspec \
        booktabs \
        tikz \
        pgf \
        xcolor \
        graphics \
        setspace \
        lipsum \
        latexmk \
        collection-fontsrecommended \
        2>/dev/null || true
    
    echo -e "${GREEN}${CHECK} LaTeX packages installed${NC}"
}

# Install LaTeX on Linux (Debian/Ubuntu)
install_latex_debian() {
    echo ""
    echo -e "${BLUE}Installing LaTeX (TeX Live)...${NC}"
    echo -e "${YELLOW}  This may take 10-15 minutes on first install.${NC}"
    echo ""
    
    if command_exists xelatex; then
        echo -e "${GREEN}${CHECK} LaTeX (XeLaTeX) already installed${NC}"
    else
        echo -e "${ARROW} Installing TeX Live via apt..."
        sudo apt-get update
        sudo apt-get install -y \
            texlive-xetex \
            texlive-latex-extra \
            texlive-fonts-extra \
            texlive-fonts-recommended \
            latexmk
        echo -e "${GREEN}${CHECK} TeX Live installed${NC}"
    fi
}

# Install LaTeX on Linux (RedHat/Fedora)
install_latex_redhat() {
    echo ""
    echo -e "${BLUE}Installing LaTeX (TeX Live)...${NC}"
    echo ""
    
    if command_exists xelatex; then
        echo -e "${GREEN}${CHECK} LaTeX (XeLaTeX) already installed${NC}"
    else
        echo -e "${ARROW} Installing TeX Live via dnf..."
        sudo dnf install -y \
            texlive-xetex \
            texlive-latex \
            texlive-collection-latexextra \
            texlive-collection-fontsextra \
            latexmk
        echo -e "${GREEN}${CHECK} TeX Live installed${NC}"
    fi
}

# Main installation
main() {
    case $OS in
        macos)
            install_homebrew
            install_latex_macos
            ;;
        debian)
            install_latex_debian
            ;;
        redhat)
            install_latex_redhat
            ;;
        *)
            echo -e "${RED}${CROSS} Unsupported OS. Please install LaTeX manually:${NC}"
            echo "   - macOS: brew install --cask mactex"
            echo "   - Ubuntu/Debian: apt install texlive-xetex texlive-latex-extra"
            echo "   - Fedora: dnf install texlive-xetex texlive-latex"
            exit 1
            ;;
    esac
    
    # Verify installation
    echo ""
    echo -e "${BLUE}Verifying installation...${NC}"
    
    if command_exists xelatex; then
        VERSION=$(xelatex --version | head -n 1)
        echo -e "${GREEN}${CHECK} XeLaTeX: ${VERSION}${NC}"
    else
        echo -e "${RED}${CROSS} XeLaTeX not found. Please restart your terminal and try again.${NC}"
        exit 1
    fi
    
    # Success message
    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                  Installation Complete! 🎉                    ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "Next steps:"
    echo -e "  ${ARROW} Create a new presentation:  ${YELLOW}./new-project.sh my-presentation${NC}"
    echo -e "  ${ARROW} Build the example:          ${YELLOW}make example${NC}"
    echo ""
    
    # Remind about terminal restart on macOS
    if [[ "$OS" == "macos" ]]; then
        echo -e "${YELLOW}Note: You may need to restart your terminal for PATH changes to take effect.${NC}"
        echo ""
    fi
}

# Run main
main


