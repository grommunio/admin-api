IN=$(wildcard rst/*.rst)
MAN=$(patsubst rst/%.rst, man/%.1, $(IN))

PANDOC_MAN=pandoc -st man

doc: man $(MAN)

man:
	mkdir -p man

man/%.1: rst/%.rst
	$(PANDOC_MAN) $< -o $@

clean:
	rm -rf man
