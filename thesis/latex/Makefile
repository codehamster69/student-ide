.PHONY: pdf watch clean
pdf:
	latexmk -pdf main.tex
watch:
	latexmk -pdf -pvc main.tex
clean:
	latexmk -C
	rm -rf build
