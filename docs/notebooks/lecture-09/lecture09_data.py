"""Load the course galaxy images and descriptors. No learning algorithm is implemented here."""

def load_galaxies():
    import os, urllib.request
    import numpy as np
    from scipy import ndimage as ndi
    from sklearn.model_selection import train_test_split
    from sklearn.impute import SimpleImputer
    SEED = 1975
    G64 = "data/galaxy10_decals_64.npz"
    H5 = "data/Galaxy10_DECals.h5"
    H5_URL = "https://zenodo.org/records/10845026/files/Galaxy10_DECals.h5?download=1"     # 2.7 GB


    def downsample_galaxy10(h5_path, out_path, chunk=500):
        """Central 128 x 128 crop of every 256 x 256 image, averaged over 2 x 2 blocks -> 64 x 64 x 3 uint8."""
        import h5py
        with h5py.File(h5_path, "r") as f:
            n = len(f["ans"]); imgs = np.empty((n, 64, 64, 3), np.uint8)
            for i in range(0, n, chunk):
                x = f["images"][i:i + chunk, 64:192, 64:192].astype(np.float32)
                imgs[i:i + chunk] = np.round(x.reshape(-1, 64, 2, 64, 2, 3).mean((2, 4))).astype(np.uint8)
            np.savez_compressed(out_path, images=imgs, labels=f["ans"][:], redshift=f["redshift"][:],
                                ra=f["ra"][:], dec=f["dec"][:], pxscale=f["pxscale"][:])


    if not os.path.exists(G64):
        if not os.path.exists(H5):
            print("downloading", H5_URL); urllib.request.urlretrieve(H5_URL, H5)
        downsample_galaxy10(H5, G64)
    with np.load(G64) as g:
        images, labels = g["images"], g["labels"].astype(int)

    DESCRIPTORS = ["mask area fraction", "brightness sum", "half-light radius r50 (px)", "axis ratio q",
                   "red-blue index", "concentration C", "centre offset (px)", "mask failure"]
    SHORT = ["area", "brightness", "r50", "q", "red-blue", "C", "offset", "failure"]


    def galaxy_features(image):
        """Eight descriptors of one 64 x 64 display image and the object mask. No label enters."""
        x = image.astype(np.float64)
        lum = x.mean(axis=2)
        border = np.r_[lum[:4].ravel(), lum[-4:].ravel(), lum[:, :4].ravel(), lum[:, -4:].ravel()]
        background = np.median(border)
        spread = 1.4826 * np.median(np.abs(border - background)) + 1.
        components, _ = ndi.label(ndi.binary_opening(lum > background + 3 * spread))
        iy, ix = np.unravel_index(np.argmax(lum[24:40, 24:40]), (16, 16))
        component = components[24 + iy, 24 + ix]
        if component == 0:
            return [np.nan] * 7 + [1.], np.zeros(lum.shape, bool)
        mask = ndi.binary_fill_holes(components == component)
        w = np.clip(lum - background, 0, None) * mask
        total = w.sum()
        yy, xx = np.indices(lum.shape)
        cy, cx = (w * yy).sum() / total, (w * xx).sum() / total
        sxx, syy = (w * (xx - cx) ** 2).sum() / total, (w * (yy - cy) ** 2).sum() / total
        sxy = (w * (xx - cx) * (yy - cy)).sum() / total
        lam = np.linalg.eigvalsh([[sxx, sxy], [sxy, syy]])
        q = np.sqrt(max(lam[0], 0) / max(lam[1], 1e-12))
        radii = np.hypot(yy - cy, xx - cx)[mask]
        order = np.argsort(radii)
        cumulative = np.cumsum(w[mask][order]) / total
        r50, r90 = radii[order][np.searchsorted(cumulative, [.5, .9])]
        sky = np.median(np.r_[x[:4].reshape(-1, 3), x[-4:].reshape(-1, 3)], axis=0)
        rgb = np.clip(x - sky, 0, None)[mask].sum(axis=0)
        colour = (rgb[0] - rgb[2]) / (rgb[0] + rgb[2] + 1e-9)
        return [mask.mean(), total / 255, r50, q, colour, r90 / max(r50, .5),
                np.hypot(cy - 31.5, cx - 31.5), 0.], mask


    CACHE = "data/galaxy10_descriptors.npy"
    if os.path.exists(CACHE):
        X_all = np.load(CACHE)
    else:
        X_all = np.array([galaxy_features(im)[0] for im in images])
        np.save(CACHE, X_all)

    perm = np.random.default_rng(0).permutation(len(labels))
    test_all, pool = np.sort(perm[:2660]), np.sort(perm[2660:])
    fit_all, val_all = train_test_split(pool, test_size=.2, stratify=labels[pool], random_state=SEED)
    smooth = lambda rows: rows[np.isin(labels[rows], [2, 3, 4])]
    fit, val, test = smooth(fit_all), smooth(val_all), smooth(test_all)
    CLASSES = np.array(["round smooth", "intermediate smooth", "cigar-shaped smooth"])
    y = labels - 2
    imputer = SimpleImputer(strategy="median").fit(X_all[fit])
    Xfit, Xval, Xtest = (imputer.transform(X_all[rows]) for rows in (fit, val, test))
    yfit, yval, ytest = y[fit], y[val], y[test]
    print("fitting / validation / test galaxies:", len(fit), len(val), len(test))
    QUERY = 0                                              # first validation galaxy, row 4234
    print("validation galaxy", val[QUERY], dict(zip(SHORT, Xval[QUERY].round(3))))
    return images, labels, X_all, DESCRIPTORS

def load_mnist():
    import os, gzip, struct, hashlib, urllib.request
    import numpy as np
    MIRROR = "https://ossci-datasets.s3.amazonaws.com/mnist/"
    FILES = {"train-images-idx3-ubyte.gz": "f68b3c2dcbeaaa9fbdd348bbdeb94873",
             "train-labels-idx1-ubyte.gz": "d53e105ee54ea40749a09fcbcd1e9432",
             "t10k-images-idx3-ubyte.gz": "9fb629c4189551a2d022fa330f9573f3",
             "t10k-labels-idx1-ubyte.gz": "ec29112dd5afa0611ce80d1b7f02629c"}
    os.makedirs("data/MNIST_raw", exist_ok=True)
    for name, md5 in FILES.items():
        target = f"data/MNIST_raw/{name}"
        if not os.path.exists(target):
            urllib.request.urlretrieve(MIRROR + name, target)
        with open(target, "rb") as f:
            assert hashlib.md5(f.read()).hexdigest() == md5, f"checksum mismatch for {name}"


    def read_idx(name):
        """Read an IDX file of unsigned bytes into an array."""
        with gzip.open(f"data/MNIST_raw/{name}", "rb") as f:
            zero, dtype, dimensions = struct.unpack(">HBB", f.read(4))
            assert zero == 0 and dtype == 8
            shape = struct.unpack(">" + "I" * dimensions, f.read(4 * dimensions))
            return np.frombuffer(f.read(), dtype=np.uint8).reshape(shape)


    images, labels = read_idx("train-images-idx3-ubyte.gz"), read_idx("train-labels-idx1-ubyte.gz")
    test_images, test_labels = read_idx("t10k-images-idx3-ubyte.gz"), read_idx("t10k-labels-idx1-ubyte.gz")
    assert images.shape == (60000, 28, 28) and test_images.shape == (10000, 28, 28)


    return images, labels, test_images, test_labels
