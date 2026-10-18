## Template 
Un template qui contient l'arborescence utilisée, qui permet d'avoir à la fois le cours, le TD, et un mix des deux, se trouve dans le dossier `template`. Au cas ou l'arborescence se serait perdue, la voici : 

```
latex/
├── commun
|   ├── config.tex
|   ├── prepacours.cls
|   └── raccourcis.sty
├── chapitre1
|   ├── chapitre1.tex
|   ├── cours
|   |   ├── contenu.tex
|   |   └── cours1.tex
|   └── TD 
|       ├── contenu_td.tex
|       └── TD1.tex
|   
└── ...
```

Le fichier `config.tex` contient les métadonnées communes à tous les fichiers, `prepacours.cls` la classe personalisée, et `raccourcis.sty` les raccourcis.
