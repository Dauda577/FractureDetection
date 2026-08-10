Place these three files here before building/deploying:

  - fracnet_main_bundle.pth   (model weights + fitted Gaussians)
  - isotonic_calibrator.pkl   (fitted isotonic regression calibrator)
  - uncertainty_thresholds.json  (OOD / aleatoric / disagreement thresholds)

All three are produced by the training notebook's calibration pipeline
and were downloaded/saved to your Kaggle dataset during development.
