# CV source

`cv.tex` is the editable source for `cv-llt.pdf`. Research publications and
manuscripts are listed separately from coursework in Project Experience,
including AskOrAct (CS6208).

Build with a TeX installation that includes XeLaTeX:

```bash
cd resume
latexmk -xelatex -interaction=nonstopmode -halt-on-error -jobname=cv-llt cv.tex
```

The same PDF is published at the repository root as `Zhu_Yufan_Resume.pdf` and
as `cv-llt.pdf` in the personal website repository.
