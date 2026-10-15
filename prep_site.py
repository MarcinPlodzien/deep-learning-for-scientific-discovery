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

# web lecture -> how its slides are made from a delivered deck. Each web lecture is compiled
# separately in a temporary copy of the deck's beamer folder: only the listed sections, its own
# subtitle and footer ("Lecture N"), and "use" files that replace sections changed after delivery.
FOLDERS = {1: "Lecture_01-02_2026.10.06", 2: "Lecture_03_2026.10.13", 3: "Lecture_04_2026.10.14", 4: "Lecture_04_2026.10.14",
           5: "Lecture_05_2026.10.20", 6: "Lecture_06_2026.10.27"}
DECKS = {
    1: dict(sections=["01a_discovery_story", "01_motivation", "02_ai_landscape", "03_learning_recipe", "04_breakthroughs", "05_closing"],
            subtitle=r"Lecture 1: & Scientific Discovery: Understanding from Data\\ & From AI to Deep Learning"),
    2: dict(sections=["03_learning_recipe", "04_mnist", "05_closing"],
            subtitle=r"Lecture 2: & The Recipe of Deep Learning"),
    3: dict(sections=["00_recap", "04b_cifar_cnn", "04c_regularisation", "04e_cam", "04g_adversarial", "05_closing"],
            subtitle=r"Lecture 3: & Convolutional Neural Networks\\ & Regularisation, Class Activation Maps\\ & Adversarial Examples and Limits"),
    4: dict(sections=["04f_blood", "04h_ising", "04i_chinese_room", "05_closing"],
            subtitle=r"Lecture 4: & CNNs on Scientific Data\\ & Blood Cells and Satellite Images\\ & Finding \(T_c\) of the 2D Ising Model"),
    5: dict(sections=["unsupervised", "closing"],
            subtitle=r"Lecture 5: & Unsupervised Learning\\ & PCA, t-SNE, Clustering, Autoencoders\\ & Blood Cells, Credit-Card Fraud and Tumour Genes without Labels"),
    6: dict(sections=["generative", "closing"],
            subtitle=r"Lecture 6: & Generative Models\\ & Variational Autoencoders, GANs, Diffusion\\ & Digits, Blood Cells and Spin Configurations"),
}

# lecture, source notebook (relative to the lecture folder), web name, title
NOTEBOOKS = [
    (1, "Lab_001_Python_Matplotlib_Pandas_warmup.ipynb", "lab-001-python-matplotlib-pandas", "Lab 001: Python, Matplotlib and Pandas"),
    (1, "Lab_002_NumPy_basics.ipynb", "lab-002-numpy", "Lab 002: NumPy"),
    (1, "Lab_003_PyTorch_basics.ipynb", "lab-003-pytorch", "Lab 003: PyTorch tensors, devices and layers"),
    (2, "Lab_004_Automatic_differentiation.ipynb", "lab-004-automatic-differentiation", "Lab 004: Automatic differentiation"),
    (2, "Lab_005_N_pendulum_SymPy_and_autodiff.ipynb", "lab-005-n-pendulum", "Lab 005: The N-link pendulum with SymPy and automatic differentiation"),
    (2, "Lab_006_UAT_and_minimizers.ipynb", "lab-006-uat-and-minimisers", "Lab 006: Universal approximation and the choice of minimiser"),
    (2, "Lab_007_Building_and_training_networks.ipynb", "lab-007-building-and-training", "Lab 007: Building and training neural networks"),
    (2, "Lab_008_Analysing_neural_networks.ipynb", "lab-008-analysing-networks", "Lab 008: Analysing a neural network"),
    (2, "Lab_009_MNIST_regression_vs_cross_entropy.ipynb", "lab-009-mnist", "Lab 009: MNIST, regression versus cross-entropy"),
    (3, "notebook_2026-10-14-limits_of_networks.ipynb", "limits-of-deep-networks", "Limits of deep networks"),
    (4, "notebook_2026-10-14-BloodMNIST_CNN_regularisation_CAM.ipynb", "bloodmnist-cnn-regularisation-cam", "Blood cells: CNNs, regularisation and class activation maps"),
    (4, "notebook_2026-10-14-convolution_and_Ising_figures.ipynb", "convolution-and-ising", "Convolution and the 2D Ising model"),
    (4, "Lab_010_Ising_Monte_Carlo_samples.ipynb", "lab-010-ising-monte-carlo", "Lab 010: Monte Carlo samples of the 2D Ising model"),
    (4, "Lab_011_CNN_Tc_from_confidence.ipynb", "lab-011-cnn-tc", "Lab 011: T_c of the 2D Ising model from the confidence of a CNN"),
    (4, "Lab_012_Onsager_exact_solution.ipynb", "lab-012-onsager", "Lab 012: Onsager's exact solution of the 2D Ising model"),
    (5, "notebook_2026-10-20-unsupervised_learning.ipynb", "unsupervised-learning", "Unsupervised learning: PCA, t-SNE, clustering, autoencoders and anomalies"),
    (6, "notebook_2026-10-27-generative_models.ipynb", "generative-models", "Generative models: probability, VAE, GAN and diffusion"),
    (6, "notebook_2026-10-27-conditional_generation.ipynb", "conditional-generation", "Conditional generation of digits and blood cells"),
]

# files published next to the notebooks: (lecture, source relative to the lecture folder, web path)
EXTRA_FILES = [
    (3, "Notebooks/results/model_E.pt", "weights/lecture-03/model_E.pt"),
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
    for f in glob.glob(os.path.join(out, "lecture-*.pdf")):
        os.remove(f)
    for lec, spec in DECKS.items():
        beamer = os.path.join(COURSE, FOLDERS[lec], "beamer")
        tmp = tempfile.mkdtemp(prefix=f"dlsd_web{lec}_")
        work = os.path.join(tmp, "beamer")
        shutil.copytree(beamer, work, ignore=shutil.ignore_patterns("*.pdf", "*.aux", "*.log", "*.nav", "*.snm", "*.toc", "*.out"))
        for target, source in spec.get("use", {}).items():
            shutil.copy(os.path.join(work, "sections", source), os.path.join(work, "sections", target))
        src = open(os.path.join(work, "main.tex")).read()
        src = re.sub(r"\\date\{[^}]*\}", r"\\date{}", src)
        src = re.sub(r"\\subtitle\{.*\}\s*$", lambda m: r"\subtitle{\begin{tabular}[t]{@{}l@{\ }l@{}}" + spec["subtitle"] + r"\end{tabular}}", src, count=1, flags=re.M)
        src = re.sub(r"Deep Learning for Scientific Discovery \\\(\\cdot\\\) Lectures? [0-9\-]+", lambda m: rf"Deep Learning for Scientific Discovery \(\cdot\) Lecture {lec}", src)
        src = re.sub(r"(?m)^\s*%?\s*\\input\{sections/[^}]*\}.*\n", "", src)
        src = src.replace("\\setcounter{section}{-1}", "")          # numbered from 0 only for the organisation part
        inputs = "".join(rf"\input{{sections/{name}}}" + "\n" for name in spec["sections"])
        src = src.replace(r"\end{document}", inputs + r"\end{document}")
        open(os.path.join(work, "main_web.tex"), "w").write(src)
        for _ in range(2):
            run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "main_web.tex"], cwd=work)
        target = os.path.join(out, f"lecture-{lec:02d}.pdf")
        run(["gs", "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.5", "-dPDFSETTINGS=/ebook",
             "-dNOPAUSE", "-dBATCH", "-dQUIET", f"-sOutputFile={target}", os.path.join(work, "main_web.pdf")])
        shutil.rmtree(tmp)
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
        folder = FOLDERS[lec]
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
                c.source = c.source.replace('"../../Lecture_04_2026.10.14/Notebooks/data/ising_Nx20_Ny20.npz"', '"data/ising_Nx20_Ny20.npz"')
                c.source = c.source.replace('"../../Lecture_07_2026.11.03/Notebooks/data/rnaseq.zip"', '"data/rnaseq.zip"')
        safe = title.replace("'", "''").replace("T_c", "Tc")
        front = nbformat.v4.new_raw_cell(f"---\ntitle: '{safe}'\n---")
        badge = nbformat.v4.new_markdown_cell(
            f'<a href="https://colab.research.google.com/github/{REPO}/blob/main/{rel}">'
            f'<img src="https://colab.research.google.com/assets/colab-badge.svg" alt="Open in Colab"></a>')
        nb.cells = [front, badge] + nb.cells
        os.makedirs(os.path.dirname(os.path.join(HERE, rel)), exist_ok=True)
        nbformat.write(nb, os.path.join(HERE, rel))
        print(f"notebook lecture {lec}: {rel}")
    for lec, src_rel, web in EXTRA_FILES:
        os.makedirs(os.path.dirname(os.path.join(HERE, web)), exist_ok=True)
        shutil.copy(os.path.join(COURSE, FOLDERS[lec], src_rel), os.path.join(HERE, web))
        print(f"file     lecture {lec}: {web}")


if __name__ == "__main__":
    what = sys.argv[1:] or ["slides", "notebooks"]
    if "slides" in what:
        build_slides()
    if "notebooks" in what:
        build_notebooks()
