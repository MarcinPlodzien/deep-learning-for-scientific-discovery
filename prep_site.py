#!/usr/bin/env python3
"""Prepare the website sources from the lecture folders of the course.

* slides: each deck is compiled once more with an empty date (the title page keeps
  everything else), Lectures 1 and 2 are split from their common deck, and the PDF is
  compressed for the web (Ghostscript, 150 dpi) into ./slides/lecture-NN.pdf;
* notebooks: copied with their stored outputs into ./notebooks/lecture-NN/<name>.ipynb,
  with a Quarto title, an "Open in Colab" badge, dates removed, and figure paths that
  work outside the course folder.

The lecture folders are never modified. Run from ./build.sh.
"""
import os, re, glob, shutil, subprocess, tempfile, sys
import nbformat

HERE = os.path.dirname(os.path.abspath(__file__))
COURSE = os.path.dirname(HERE)
REPO = "MarcinPlodzien/deep-learning-for-scientific-discovery"

# lecture -> (folder, pages of the deck or None for all)
DECKS = {
    1: ("Lecture_01-02_2026.10.06", "1-13,last"),
    2: ("Lecture_01-02_2026.10.06", "1,14-last"),
    3: ("Lecture_03_2026.10.13", None),
    4: ("Lecture_04_2026.10.14", None),
}

# lecture, source notebook (relative to the lecture folder), web name, title
NOTEBOOKS = [
    (2, "Lab_001_Python_Matplotlib_Pandas_warmup.ipynb", "lab-001-python-matplotlib-pandas", "Lab 001: Python, Matplotlib and Pandas"),
    (2, "Lab_002_NumPy_basics.ipynb", "lab-002-numpy", "Lab 002: NumPy, thinking in arrays"),
    (2, "Lab_003_PyTorch_basics.ipynb", "lab-003-pytorch", "Lab 003: PyTorch tensors, devices and layers"),
    (3, "Lab_004_Automatic_differentiation.ipynb", "lab-004-automatic-differentiation", "Lab 004: Automatic differentiation"),
    (3, "Lab_005_N_pendulum_SymPy_and_autodiff.ipynb", "lab-005-n-pendulum", "Lab 005: The N-link pendulum with SymPy and automatic differentiation"),
    (3, "Lab_006_UAT_and_minimizers.ipynb", "lab-006-uat-and-minimisers", "Lab 006: Universal approximation and the choice of minimiser"),
    (3, "Lab_007_Building_and_training_networks.ipynb", "lab-007-building-and-training", "Lab 007: Building and training neural networks"),
    (3, "Lab_008_Analysing_neural_networks.ipynb", "lab-008-analysing-networks", "Lab 008: Analysing a neural network"),
    (3, "Lab_009_MNIST_regression_vs_cross_entropy.ipynb", "lab-009-mnist", "Lab 009: MNIST, regression versus cross-entropy"),
    (4, "notebook_2026-10-14-BloodMNIST_CNN_regularisation_CAM.ipynb", "bloodmnist-cnn-regularisation-cam", "Blood cells: CNNs, regularisation and class activation maps"),
    (4, "notebook_2026-10-14-convolution_and_Ising_figures.ipynb", "convolution-and-ising", "Convolution and the 2D Ising model: the figures of the lecture"),
    (4, "Lab_010_Ising_Monte_Carlo_samples.ipynb", "lab-010-ising-monte-carlo", "Lab 010: Monte Carlo samples of the 2D Ising model"),
    (4, "Lab_011_CNN_Tc_from_confidence.ipynb", "lab-011-cnn-tc", "Lab 011: T_c of the 2D Ising model from the confidence of a CNN"),
    (4, "Lab_012_Onsager_exact_solution.ipynb", "lab-012-onsager", "Lab 012: Onsager's exact solution of the 2D Ising model"),
]

MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
DATE_PATTERNS = [
    r"\s*\(\d{1,2}\.\d{1,2}\.\d{4}\)",                 # " (14.10.2026)"
    r"\s*\b\d{1,2}\.\d{1,2}\.\d{4}\b",                 # "14.10.2026"
    r"\s*\b\d{4}-\d{2}-\d{2}\b",                       # "2026-10-14"
    rf"\s*\b\d{{1,2}} (?:{MONTHS}) \d{{4}}\b",         # "14 October 2026"
]


def run(cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"command failed: {' '.join(cmd)}\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
    return r.stdout


def build_slides():
    out = os.path.join(HERE, "slides"); os.makedirs(out, exist_ok=True)
    compiled = {}
    for lec, (folder, pages) in DECKS.items():
        beamer = os.path.join(COURSE, folder, "beamer")
        if folder not in compiled:
            src = open(os.path.join(beamer, "main.tex")).read()
            web = re.sub(r"\\date\{[^}]*\}", r"\\date{}", src)
            tmp = tempfile.mkdtemp(prefix="dlsd_web_")
            texfile = os.path.join(beamer, "main_web.tex")
            open(texfile, "w").write(web)
            try:
                for _ in range(2):
                    run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", f"-output-directory={tmp}", "main_web.tex"], cwd=beamer)
            finally:
                os.remove(texfile)
            compiled[folder] = os.path.join(tmp, "main_web.pdf")
        pdf = compiled[folder]
        if pages:
            n = int(re.search(r"Pages:\s+(\d+)", run(["pdfinfo", pdf])).group(1))
            sel = []
            for part in pages.split(","):
                part = part.replace("last", str(n))
                a, _, b = part.partition("-")
                sel += list(range(int(a), int(b or a) + 1))
            tmp = tempfile.mkdtemp(prefix="dlsd_split_")
            run(["pdfseparate", pdf, os.path.join(tmp, "p-%03d.pdf")])
            part_pdf = os.path.join(tmp, "part.pdf")
            run(["pdfunite"] + [os.path.join(tmp, f"p-{i:03d}.pdf") for i in sel] + [part_pdf])
            pdf = part_pdf
        target = os.path.join(out, f"lecture-{lec:02d}.pdf")
        run(["gs", "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.5", "-dPDFSETTINGS=/ebook",
             "-dNOPAUSE", "-dBATCH", "-dQUIET", f"-sOutputFile={target}", pdf])
        print(f"slides  lecture {lec}: {os.path.getsize(target) / 1e6:.1f} MB")


def strip_dates(text):
    lines = [l for l in text.split("\n") if not re.match(r"^\s*\*?Notebook for the lecture of .*$", l)]
    text = "\n".join(lines)
    for p in DATE_PATTERNS:
        text = re.sub(p, "", text)
    return text


def build_notebooks():
    dst = os.path.join(HERE, "notebooks")
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    for lec, src_name, web_name, title in NOTEBOOKS:
        folder = DECKS[lec][0]
        src = os.path.join(COURSE, folder, "Notebooks", src_name)
        nb = nbformat.read(src, as_version=4)
        rel = f"notebooks/lecture-{lec:02d}/{web_name}.ipynb"
        for c in nb.cells:
            if c.cell_type == "markdown":
                c.source = strip_dates(c.source)
                c.source = re.sub(r"(?m)^\s*---\s*$", "<hr/>", c.source)
            elif c.cell_type == "code":
                c.source = c.source.replace('OUT = "../beamer/figures"',
                                            'import os\nOUT = "figures"; os.makedirs(OUT, exist_ok=True)')
                c.source = c.source.replace('"../../Lecture_04_2026.10.14/Notebooks/data/bloodmnist.npz"', '"data/bloodmnist.npz"')
        safe = title.replace("'", "''").replace("T_c", "Tc")
        front = nbformat.v4.new_raw_cell(f"---\ntitle: '{safe}'\n---")
        badge = nbformat.v4.new_markdown_cell(
            f'<a href="https://colab.research.google.com/github/{REPO}/blob/main/{rel}">'
            f'<img src="https://colab.research.google.com/assets/colab-badge.svg" alt="Open in Colab"></a>')
        nb.cells = [front, badge] + nb.cells
        os.makedirs(os.path.dirname(os.path.join(HERE, rel)), exist_ok=True)
        nbformat.write(nb, os.path.join(HERE, rel))
        print(f"notebook lecture {lec}: {rel}")


if __name__ == "__main__":
    what = sys.argv[1:] or ["slides", "notebooks"]
    if "slides" in what:
        build_slides()
    if "notebooks" in what:
        build_notebooks()
