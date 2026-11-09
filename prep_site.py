#!/usr/bin/env python3
"""Prepare the website sources from the lecture folders of the course.

* slides: each deck is compiled once more with an empty date (the title page keeps
  everything else), Lectures 1 and 2 are split from their common deck, and the PDF is
  compressed for the web (Ghostscript, 150 dpi) into ./slides/lecture-NN.pdf;
* notebooks: copied with their stored outputs into ./notebooks/lecture-NN/<name>.ipynb,
  with a Quarto title, an "Open in Colab" badge and dates removed.

The lecture folders are never modified. Run from ./build.sh.
"""
import os, re, glob, shutil, subprocess, tempfile, sys, json
from urllib.parse import unquote
import nbformat

HERE = os.path.dirname(os.path.abspath(__file__))
COURSE = os.path.dirname(HERE)
REPO = "MarcinPlodzien/deep-learning-for-scientific-discovery"

# web lecture -> how its slides are made from a delivered deck. Each web lecture is compiled
# separately in a temporary copy of the deck's beamer folder: only the listed sections, its own
# subtitle and footer ("Lecture N"), and "use" files that replace sections changed after delivery.
FOLDERS = {1: "Lecture_01-02_2026.10.06", 2: "Lecture_03_2026.10.13", 3: "Lecture_04_2026.10.14", 4: "Lecture_04_2026.10.14",
           5: "Lecture_05_2026.10.20", 6: "Lecture_06_2026.10.21", 7: "Lecture_07_2026.10.27",
           9: "Lecture_09_decision_trees_2026.11.10",
           10: "Lecture_10_reinforcement_learning_2026.11.17"}
DECKS = {
    1: dict(sections=["01a_discovery_story", "01_motivation", "02_ai_landscape", "03_learning_recipe", "04_breakthroughs", "05_closing"],
            subtitle=r"Lecture 1: & AI and Machine Learning\\ & Paradigms and Scientific Discovery"),
    2: dict(sections=["03_learning_recipe", "04_mnist", "05_closing"],
            subtitle=r"Lecture 2: & Supervised Learning\\ & The Recipe of Deep Learning"),
    3: dict(sections=["00_recap", "04b_cifar_cnn", "04c_regularisation", "04e_cam", "04g_adversarial", "05_closing"], use={"05_closing.tex": "05_closing_web3.tex"},
            subtitle=r"Lecture 3: & Supervised Learning on Images\\ & Convolutional Neural Networks and Regularisation\\ & Class Activation Maps, Adversarial Examples, Limits"),
    4: dict(sections=["04f_blood", "04j_transfer", "04h_ising", "04i_chinese_room", "05_closing"], use={"05_closing.tex": "05_closing_web4.tex"},
            subtitle=r"Lecture 4: & Supervised Learning\\ & CNNs on Scientific Images\\ & Blood Cells, Satellites, Transfer Learning\\ & Finding \(T_c\) of the 2D Ising Model"),
    5: dict(sections=["unsupervised", "closing", "backup"],
            subtitle=r"Lecture 5: & Unsupervised Learning I\\ & PCA, t-SNE, Autoencoders, Anomaly Detection\\ & Blood Cells, Fraud and Tumour Genes"),
    6: dict(sections=["macros_nn", "l6_vae", "closing_l6"],
            subtitle=r"Lecture 6: & Unsupervised Learning II\\ & Probability and Variational Autoencoders\\ & Conditional and Disentangled Generation\\ & Digits, Blood Cells, Ising Configurations, Galaxies"),
    7: dict(sections=["problem", "chaos", "linear", "nvar", "networks", "knowledge", "datasets", "closing"],
            subtitle=r"Lecture 7: & Time Series\\ & AR, MA, ARMA and NVAR\\ & MLP, RNN and LSTM\\ & Neural ODEs and Physics-Informed Networks"),
    9: dict(as_is=True),
    10: dict(sections=["recap", "motivation", "setting", "values", "bellman", "td", "qlearning", "policygradient", "deepq", "closing", "appendix"],
             subtitle=r"Lecture 10: & Reinforcement Learning\\ & Value Functions and Bellman Equations\\ & Q-Learning and Policy Gradients\\ & Deep Networks in Place of Tables"),    # deck written as one main.tex with title, footer "Lecture 9" and no lecture date
}

# lecture, source notebook (relative to the lecture folder), web name, title[, lecture folder if not FOLDERS[lecture]]
NOTEBOOKS = [
    (1, "Lab_001_Python_Matplotlib_Pandas_warmup.ipynb", "lab-001-python-matplotlib-pandas", "Lab 001: Python, Matplotlib and Pandas"),
    (1, "Lab_002_NumPy_basics.ipynb", "lab-002-numpy", "Lab 002: NumPy"),
    (1, "Lab_003_PyTorch_basics.ipynb", "lab-003-pytorch", "Lab 003: PyTorch tensors, devices and layers"),
    (2, "Lab_004_Automatic_differentiation.ipynb", "lab-004-automatic-differentiation", "Lab 004: Automatic differentiation"),
    (2, "Lab_005_N_pendulum_SymPy_and_autodiff.ipynb", "lab-005-n-pendulum", "Lab 005: The N-link pendulum with SymPy and automatic differentiation"),
    (2, "Lab_004_Universal_approximation_steps.ipynb", "universal-approximation-steps", "Universal approximation from step functions", "Lecture_01-02_2026.10.06"),
    (2, "Lab_006_UAT_and_minimizers.ipynb", "lab-006-uat-and-minimisers", "Lab 006: Universal approximation and the choice of minimiser"),
    (2, "Lab_007_Building_and_training_networks.ipynb", "lab-007-building-and-training", "Lab 007: Building and training neural networks"),
    (2, "Lab_008_Analysing_neural_networks.ipynb", "lab-008-analysing-networks", "Lab 008: Analysing a neural network"),
    (2, "Lab_009_MNIST_regression_vs_cross_entropy.ipynb", "lab-009-mnist", "Lab 009: MNIST, regression versus cross-entropy"),
    (3, "notebook_2026-10-14-limits_of_networks.ipynb", "limits-of-deep-networks", "Limits of deep networks"),
    (3, "Lab_013a_CNN_on_MNIST_and_CIFAR10_PyTorch.ipynb", "lab-013a-cnn-pytorch", "Lab 013a: CNNs on MNIST and CIFAR-10 in PyTorch"),
    (3, "Lab_013b_CNN_on_MNIST_and_CIFAR10_JAX.ipynb", "lab-013b-cnn-jax", "Lab 013b: CNNs on MNIST and CIFAR-10 in JAX"),
    (3, "notebook_2026-10-14-cam_cifar10.ipynb", "cam-cifar10", "Class activation maps of a CIFAR-10 CNN"),
    (4, "notebook_2026-10-14-BloodMNIST_CNN_regularisation_CAM.ipynb", "bloodmnist-cnn-regularisation-cam", "Blood cells: CNNs, regularisation and class activation maps"),
    (4, "notebook_2026-10-14-convolution_and_Ising_figures.ipynb", "convolution-and-ising", "Convolution and the 2D Ising model"),
    (4, "Lab_010_Ising_Monte_Carlo_samples.ipynb", "lab-010-ising-monte-carlo", "Lab 010: Monte Carlo samples of the 2D Ising model"),
    (4, "Lab_011_CNN_Tc_from_confidence.ipynb", "lab-011-cnn-tc", "Lab 011: T_c of the 2D Ising model from the confidence of a CNN"),
    (4, "Lab_012_Onsager_exact_solution.ipynb", "lab-012-onsager", "Lab 012: Onsager's exact solution of the 2D Ising model"),
    (4, "Lab_014a_Transfer_learning_PyTorch.ipynb", "lab-014a-transfer-pytorch", "Lab 014a: Transfer learning in PyTorch"),
    (4, "Lab_014b_Transfer_learning_JAX.ipynb", "lab-014b-transfer-jax", "Lab 014b: Transfer learning in JAX"),
    (5, "notebook_2026-10-20-unsupervised_learning.ipynb", "unsupervised-learning", "Unsupervised learning: PCA, t-SNE, clustering, autoencoders and anomalies"),
    (6, "notebook_2026-10-27-generative_models.ipynb", "generative-models", "Generative models: probability, autoencoder and VAE"),
    (6, "notebook_2026-10-27-conditional_generation.ipynb", "conditional-generation", "Conditional generation of digits and blood cells"),
    (6, "notebook_2026-10-27-latent_space.ipynb", "latent-space", "Latent space of a VAE for a curve and a bar"),
    (6, "notebook_2026-10-27-beta_vae.ipynb", "beta-vae", "Disentangled latent features with the beta-VAE"),
    (6, "notebook_2026-10-27-ising_cvae.ipynb", "ising-cvae", "Ising configurations from a conditional VAE"),
    (6, "notebook_2026-10-27-interpretability_beta_vae.ipynb", "galaxy-beta-vae", "Galaxies with a beta-VAE: latent factors and counterfactuals"),
    (6, "Lab_015_Physical_parameters_from_trajectories.ipynb", "lab-015-trajectories", "Lab 015: Physical parameters from trajectories"),
    (7, "notebook_2026-10-27-signals_lorenz_mackey_glass_santa_fe.ipynb", "signals-and-predictability", "Signals and their predictability"),
    (7, "notebook_2026-10-27-ar_ma_arma_nvar.ipynb", "linear-models-and-nvar", "Linear models and NVAR"),
    (7, "notebook_2026-10-27-mlp_forecaster.ipynb", "mlp-forecaster", "Multilayer perceptron forecaster"),
    (7, "notebook_2026-10-27-rnn_forecaster.ipynb", "rnn-forecaster", "Recurrent network forecaster"),
    (7, "notebook_2026-10-27-lstm_forecaster.ipynb", "lstm-forecaster", "LSTM forecaster"),
    (7, "notebook_2026-10-27-comparison_of_models.ipynb", "comparison-of-models", "Comparison of forecasting models"),
    (7, "notebook_2026-10-27-koopman_operator.ipynb", "koopman-operator", "Koopman operator"),
    (7, "notebook_2026-10-27-neural_ode.ipynb", "neural-ode", "Neural ordinary differential equations"),
    (7, "notebook_2026-10-27-pendulum_with_unknown_friction.ipynb", "pendulum-unknown-friction", "Pendulum with unknown friction"),
    (7, "notebook_2026-10-27-physics_informed_networks.ipynb", "physics-informed-networks", "Physics-informed neural networks"),
    (7, "notebook_2026-10-27-central_england_temperature.ipynb", "central-england-temperature", "Forecasting the weather in central England"),
    (7, "notebook_2026-10-27-sunspots.ipynb", "sunspots", "Forecasting the sunspot number"),
    (7, "notebook_2026-10-27-exercise_sp500.ipynb", "exercise-sp500", "Exercise: forecasting the S&P 500 index"),
    (7, "notebook_2026-10-27-exercise_enso.ipynb", "exercise-enso", "Exercise: forecasting El Niño"),
    (9, "notebook_2026-11-10-00-tree_foundations.ipynb", "tree-foundations", "Decision trees with scikit-learn"),
    (9, "notebook_2026-11-10-galaxy_classification_tree.ipynb", "galaxy-classification-tree", "Galaxies: a classification tree"),
    (9, "notebook_2026-11-10-galaxy_forests_networks.ipynb", "galaxy-forests-networks", "Galaxies: random forests and a neural network"),
    (9, "notebook_2026-11-10-diabetes_regression_tree.ipynb", "diabetes-regression-tree", "Regression tree for diabetes progression"),
    (9, "notebook_2026-11-10-diabetes_progression_classes.ipynb", "diabetes-progression-classes", "Classifying progression above a reference score"),
    (9, "notebook_2026-11-10-iris_classification_tree.ipynb", "iris-classification-tree", "Impurity measures and a tree for the Iris flowers"),
    (9, "notebook_2026-11-10-iris_diabetes_forests.ipynb", "iris-diabetes-forests", "Random forests for classes and numbers"),
    (9, "notebook_2026-11-10-trees_forests_neural_networks.ipynb", "trees-forests-neural-networks", "Trees, forests and small neural networks compared"),
    (9, "notebook_2026-11-10-concentration_response_tree.ipynb", "concentration-response-tree", "Predicting a concentration response"),
    (9, "notebook_2026-11-10-breast_cancer_tree.ipynb", "breast-cancer-tree", "Breast-cancer cell nuclei"),
    (9, "notebook_2026-11-10-mnist_trees.ipynb", "mnist-trees", "Three methods for handwritten digits"),
    (10, "notebook_2026-11-17-gridworld_bellman.ipynb", "gridworld-bellman", "Value functions and Bellman equations on a gridworld"),
    (10, "notebook_2026-11-17-policy_gradient_cartpole.ipynb", "policy-gradient-cartpole", "Policy gradient on the cart-pole"),
    (10, "notebook_2026-11-17-dqn_lunar_lander.ipynb", "dqn-lunar-lander", "Deep Q-learning on the Lunar Lander"),
]

# Lecture notes are published only for chapters that Marcin has approved (L7 2026-10-29; L5, L6, L9, L10 2026-11-09).
# files published next to the notebooks: (lecture, source relative to the lecture folder, web path)
EXTRA_FILES = [
    (3, "Notebooks/results/model_E.pt", "weights/lecture-03/model_E.pt"),
    (3, "Notebooks/results/cam_cifar_gap_cnn.pt", "weights/lecture-03/cam_cifar_gap_cnn.pt"),
    (5, "lecture_notes/lecture_05_notes.pdf", "notes/lecture-05.pdf"),
    (6, "lecture_notes/lecture_06_notes.pdf", "notes/lecture-06.pdf"),
    (7, "lecture_notes/lecture_07_notes.pdf", "notes/lecture-07.pdf"),
    (9, "lecture_notes/lecture_09_notes.pdf", "notes/lecture-09.pdf"),
    (10, "lecture_notes/lecture_10_notes.pdf", "notes/lecture-10.pdf"),
    (9, "Notebooks/lecture09_data.py", "notebooks/lecture-09/lecture09_data.py"),
    (9, "Notebooks/data/galaxy10_measurements.csv", "notebooks/lecture-09/data/galaxy10_measurements.csv"),
]

MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
DATE_PATTERNS = [   # only dates of the course years (lecture dates); dates of data are kept
    r"\s*\(\d{1,2}\.\d{1,2}\.202[67]\)",                 # " (14.10.2026)"
    r"\s*\b\d{1,2}\.\d{1,2}\.202[67]\b",                 # "14.10.2026"
    r"\s*\b202[67]-\d{2}-\d{2}\b",                       # "2026-10-14"
    rf"\s*\b\d{{1,2}} (?:{MONTHS}) 202[67]\b",         # "14 October 2026"
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
        aux = shutil.ignore_patterns("*.aux", "*.log", "*.nav", "*.snm", "*.toc", "*.out")
        def skip(d, names, root=beamer):
            # compiled decks in the beamer folder itself are skipped; PDF figures in subfolders are kept
            pdfs = {f for f in names if f.endswith(".pdf")} if os.path.samefile(d, root) else set()
            return set(aux(d, names)) | pdfs
        shutil.copytree(beamer, work, ignore=skip)
        for target, source in spec.get("use", {}).items():
            shutil.copy(os.path.join(work, "sections", source), os.path.join(work, "sections", target))
        src = open(os.path.join(work, "main.tex")).read()
        if spec.get("as_is"):
            open(os.path.join(work, "main_web.tex"), "w").write(src)
        else:
            src = web_source(src, spec, lec)
            open(os.path.join(work, "main_web.tex"), "w").write(src)
        for _ in range(2):
            run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "main_web.tex"], cwd=work)
        target = os.path.join(out, f"lecture-{lec:02d}.pdf")
        run(["gs", "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.5", "-dPDFSETTINGS=/ebook",
             "-dNOPAUSE", "-dBATCH", "-dQUIET", f"-sOutputFile={target}", os.path.join(work, "main_web.pdf")])
        shutil.rmtree(tmp)
        print(f"slides  lecture {lec}: {os.path.getsize(target) / 1e6:.1f} MB")


def web_source(src, spec, lec):
    if True:
        src = re.sub(r"\\date\{[^}]*\}", r"\\date{}", src)
        src = re.sub(r"\\subtitle\{.*\}\s*$", lambda m: r"\subtitle{\begin{tabular}[t]{@{}l@{\ }l@{}}" + spec["subtitle"] + r"\end{tabular}}", src, count=1, flags=re.M)
        src = re.sub(r"Deep Learning for Scientific Discovery \\\(\\cdot\\\) Lectures? [0-9\-]+", lambda m: rf"Deep Learning for Scientific Discovery \(\cdot\) Lecture {lec}", src)
        src = re.sub(r"(?m)^\s*%?\s*\\input\{sections/[^}]*\}.*\n", "", src)
        src = src.replace("\\setcounter{section}{-1}", "")          # numbered from 0 only for the organisation part
        inputs = "".join(rf"\input{{sections/{name}}}" + "\n" for name in spec["sections"])
        src = src.replace(r"\end{document}", inputs + r"\end{document}")
    return src


def strip_dates(text):
    lines = [l for l in text.split("\n") if not re.match(r"^\s*\*?Notebook for the lecture of .*$", l)]
    text = "\n".join(lines)
    # keep dates that belong to a data range ("from 1 Jan 1772 to 26 Oct 2026", "2016 – 2026")
    range_word = re.compile(r"(?:\b(?:from|to|until|between|and|since)|[–-])\s*$", re.I)
    range_next = re.compile(r"^\s*(?:\bto\b|\band\b|[–-])", re.I)
    def drop(m):
        before, after = m.string[:m.start()], m.string[m.end():]
        if range_word.search(before[-12:] + m.group(0)[:len(m.group(0)) - len(m.group(0).lstrip())]) or range_next.match(after):
            return m.group(0)
        return ""
    for p in DATE_PATTERNS:
        text = re.sub(p, drop, text)
    return text


def build_notebooks(lectures=None):
    dst = os.path.join(HERE, "notebooks")
    if lectures is None and os.path.isdir(dst):
        shutil.rmtree(dst)
    for lec, src_name, web_name, title, *own_folder in NOTEBOOKS:
        if lectures is not None and lec not in lectures:
            continue
        folder = own_folder[0] if own_folder else FOLDERS[lec]
        src = os.path.join(COURSE, folder, "Notebooks", src_name)
        nb = nbformat.read(src, as_version=4)
        rel = f"notebooks/lecture-{lec:02d}/{web_name}.ipynb"
        for c in nb.cells:
            if c.cell_type == "markdown":
                c.source = strip_dates(c.source)
                c.source = re.sub(r"(?m)^\s*---\s*$", "<hr/>", c.source)
                if lec == 9:
                    for number, source_name, slug, *_ in NOTEBOOKS:
                        if number == 9:
                            c.source = c.source.replace(source_name, slug + ".ipynb")
        safe = title.replace("'", "''").replace("T_c", "Tc")
        front = nbformat.v4.new_raw_cell(f"---\ntitle: '{safe}'\n---")
        badge = nbformat.v4.new_markdown_cell(
            f'<a href="https://colab.research.google.com/github/{REPO}/blob/main/{rel}">'
            f'<img src="https://colab.research.google.com/assets/colab-badge.svg" alt="Open in Colab"></a>')
        support = []
        if lec == 9:
            all_source = "\n".join(c.source for c in nb.cells)
            files = []
            if "from lecture09_data import" in all_source:
                files.append("lecture09_data.py")
            if "galaxy10_measurements.csv" in all_source or "load_galaxies" in all_source:
                files.append("data/galaxy10_measurements.csv")
            if files:
                support.append(nbformat.v4.new_code_cell(
                    "#| code-fold: true\n#| code-summary: Load supporting course files when running in Colab\n"
                    "from pathlib import Path\nfrom urllib.request import urlretrieve\n"
                    f"for name in {files!r}:\n"
                    "    target = Path(name)\n"
                    "    if not target.exists():\n"
                    "        target.parent.mkdir(parents=True, exist_ok=True)\n"
                    f"        urlretrieve('https://raw.githubusercontent.com/{REPO}/main/notebooks/lecture-09/' + name, target)"))
        nb.cells = [front, badge] + support + nb.cells
        os.makedirs(os.path.dirname(os.path.join(HERE, rel)), exist_ok=True)
        nbformat.write(nb, os.path.join(HERE, rel))
        print(f"notebook lecture {lec}: {rel}")
    for lec, src_rel, web in EXTRA_FILES:
        if lectures is not None and lec not in lectures:
            continue
        os.makedirs(os.path.dirname(os.path.join(HERE, web)), exist_ok=True)
        shutil.copy(os.path.join(COURSE, FOLDERS[lec], src_rel), os.path.join(HERE, web))
        print(f"file     lecture {lec}: {web}")


def clean_search_index(lecture=9):
    """Remove obsolete section anchors retained by incremental Quarto renders."""
    path = os.path.join(HERE, "docs", "search.json")
    if not os.path.exists(path):
        return
    entries = json.load(open(path))
    keep, ids = [], {}
    for entry in entries:
        href = entry.get("href", "")
        page, _, anchor = href.partition("#")
        affected = (page == f"lectures/lecture-{lecture:02d}.html"
                    or page.startswith(f"notebooks/lecture-{lecture:02d}/"))
        if affected and anchor:
            if page not in ids:
                filename = os.path.join(HERE, "docs", page)
                ids[page] = set(re.findall(r'\bid="([^"]+)"', open(filename).read())) if os.path.exists(filename) else set()
            if unquote(anchor) not in ids[page]:
                continue
        keep.append(entry)
    with open(path, "w") as output:
        json.dump(keep, output, ensure_ascii=False, indent=2)
    print(f"search   removed {len(entries) - len(keep)} obsolete lecture-{lecture:02d} anchors")


if __name__ == "__main__":
    what = sys.argv[1:] or ["slides", "notebooks"]
    if "slides" in what:
        build_slides()
    if "notebooks" in what:
        build_notebooks()
    if "clean-search" in what:
        clean_search_index()
