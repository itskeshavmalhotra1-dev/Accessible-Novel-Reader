# Accessible Novel Reader

A clean, accessible desktop application in Python for browsing online light novels and web novels, browsing by category/genre, and reading chapter-by-chapter with screen readers (NVDA, JAWS) and full keyboard navigation.

## Features

- **Online Sources**: FreeWebNovel, NovelFull, NovGo, NovelPing.
- **Categories & Genres**: Browse by Latest Release, Most Popular, Completed, or any genre (Action, Fantasy, Romance, Sci-fi, etc.).
- **Reading Section**: Multi-line reading text area with Up/Down arrow line navigation for screen readers.
- **Next & Previous Chapter**: Quick navigation buttons right beside the reading section (`Alt+N` and `Alt+P`).
- **Screen Reader Support**: Integrated with `accessible-output2` and acoustic earcons (`winsound.Beep`).
- **Zero Terminal**: Launches purely as a GUI without leaving any open terminal/command prompt window.

## How to Run

- **Direct Launch (Recommended)**: Double-click `run.vbs` or `run.bat` (launches GUI silently without command prompt).
- **Direct Python**: Double-click `main.pyw` or run `python main.py`.

## Keyboard Shortcuts

- `PageDown`: Next Page of novels
- `PageUp`: Previous Page of novels
- `Alt + N`: Next Chapter
- `Alt + P`: Previous Chapter
- `F5`: Reload source / categories

Use `Tab` and `Shift + Tab` to navigate seamlessly between all sections and controls.

## Disclaimer & Legal

This project is an open-source accessibility client created for personal, educational, and assistive technology research purposes. 

- This software does **not** host, store, index, or distribute any copyrighted novel texts or media.
- All novel metadata and chapter texts are retrieved on-the-fly client-side from publicly accessible web pages solely upon user interaction.
- The authors and contributors do not claim ownership of any content accessed through third-party sources. All rights belong to their respective authors and copyright owners.

## License

MIT License. See [LICENSE](LICENSE) for details.
