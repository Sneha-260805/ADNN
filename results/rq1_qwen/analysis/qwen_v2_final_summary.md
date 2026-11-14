# RQ1 — Qwen 2.5-7B-Instruct Final Results
## 1. Final Binary Probe
The final binary linear-probe evaluation using Qwen 2.5-7B-Instruct hidden states achieved:
| Metric | Result |
|---|---:|
| Balanced Accuracy | 0.9117647059 |
| Macro F1 | 0.8838162931 |
| AUROC | 0.9864234910 |
## 2. Lexical Baseline
| Metric | Result |
|---|---:|
| Accuracy | 0.7600000000 |
| Balanced Accuracy | 0.7438725490 |
| Macro F1 | 0.7417429225 |
| AUROC | 0.8710351788 |
Per-class results:
| Class | Precision | Recall | F1 |
|---|---:|---:|---:|
| Non-irreversible | 0.8195488722 | 0.8014705882 | 0.8104089219 |
| Irreversible | 0.6603773585 | 0.6862745098 | 0.6730769231 |
Confusion matrix:
[[218, 54],
 [48, 105]]
## 3. Mean Action-Token Representation
| Metric | Result |
|---|---:|
| Accuracy | 0.8729411765 |
| Balanced Accuracy | 0.9007352941 |
| Macro F1 | 0.8698979592 |
| AUROC | 0.9883217993 |
## 4. Horizon Ablation
All horizon ablations use the last action token from layer 18.
| Horizon | Accuracy | Balanced Accuracy | Macro F1 | AUROC |
|---|---:|---:|---:|---:|
| H1 | 0.8941176471 | 0.9172794118 | 0.8908072555 | 0.9883938870 |
| H2 | 0.8870588235 | 0.9117647059 | 0.8838162931 | 0.9864234910 |
| H3 | 0.8871 | 0.9118 | 0.8838 | 0.9864 |
H1 gives the highest balanced accuracy.
## 5. Bootstrap 95% Confidence Intervals
| Metric | Estimate | 95% CI |
|---|---:|---:|
| Balanced Accuracy | 0.9117647059 | [0.8110891089, 1.0000000000] |
| Macro F1 | 0.8838162931 | [0.7864901380, 1.0000000000] |
| AUROC | 0.9864234910 | [0.9424199731, 1.0000000000] |
## 6. Minimal-Pair Evaluation
| Metric | Result |
|---|---:|
| Pair Accuracy | 0.3174603175 |
| Contrast-Preservation Accuracy | 0.3174603175 |
| Balanced Accuracy | 0.7345679012 |
| Macro F1 | 0.6921087962 |
## 7. Main Comparison
| Evaluation | Balanced Accuracy | Macro F1 | AUROC |
|---|---:|---:|---:|
| Qwen hidden-state probe | 0.9118 | 0.8838 | 0.9864 |
| Lexical baseline | 0.7439 | 0.7417 | 0.8710 |
| Mean action tokens | 0.9007 | 0.8699 | 0.9883 |
| Minimal-pair evaluation | 0.7346 | 0.6921 | — |
The final hidden-state probe substantially outperforms the lexical action-text baseline under the standard evaluation. However, performance drops substantially under the controlled minimal-pair evaluation, indicating that aggregate decoding may partly reflect action identity, contextual information, or other correlated cues.
## 8. Scientific Interpretation
Qwen 2.5-7B-Instruct hidden states contain substantial information predictive of action reversibility under the standard evaluation. The binary hidden-state probe achieves a balanced accuracy of 0.9118 and AUROC of 0.9864, substantially exceeding the lexical action-text baseline.
However, the controlled minimal-pair evaluation is substantially weaker, with balanced accuracy of 0.7346 and pair/contrast-preservation accuracy of 0.3175. Therefore, strong aggregate decoding should not by itself be interpreted as proof of a clean, reversibility-specific representation.
### Final conclusion
Qwen 2.5-7B-Instruct hidden states contain substantial information predictive of action reversibility under the standard evaluation, substantially outperforming the lexical action-text baseline. However, performance drops substantially under the controlled minimal-pair evaluation, indicating that aggregate decoding may partly reflect action identity, contextual information, or other correlated cues rather than a robust reversibility-specific representation.
## 9. Reproducibility
Final notebook:
notebooks/qwen-rq1-v2.ipynb
Result artifacts:
results/rq1_qwen/
Large hidden-state arrays (.npy) are intentionally excluded from Git according to the repository .gitignore. Associated extraction metadata/manifests can document the local artifacts.
## 10. Status
**FINAL**
These results supersede the earlier preliminary_v1.0 summary. The binary probe, lexical baseline, mean action-token analysis, horizon ablations, bootstrap confidence intervals, and minimal-pair evaluation above are the authoritative final RQ1 results for this Qwen experiment.
