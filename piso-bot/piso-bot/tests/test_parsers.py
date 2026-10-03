from piso_bot.parsers import extract_listings, parse_price, parse_rooms

HABITACLIA_HTML = """
<html><body>
<article class="js-list-item">
  <a href="/alquiler-piso-turo_de_la_peira-barcelona-i1234567890123.htm"><img src="https://img.example.com/a.jpg"></a>
  <h3><a href="/alquiler-piso-turo_de_la_peira-barcelona-i1234567890123.htm">Piso en Turó de la Peira, Barcelona</a></h3>
  <p>1.200 € · 2 hab. · 1 baño · 60 m² · 20,00 €/m² Amueblado, larga duración</p>
</article>
<article class="js-list-item">
  <a href="/alquiler-piso-badalona-i9999999999999.htm">Piso en Llefià</a>
  <p>783 € 2 habitaciones 50 m² 15,66 €/m²</p>
</article>
<a href="/otra-cosa.htm">sin relación</a>
</body></html>
"""


def test_parse_price_ignores_price_per_m2():
    assert parse_price("18,74 €/m² 1.250 €") == 1250
    assert parse_price("850€ al mes") == 850
    assert parse_price("sin precio") is None


def test_parse_rooms():
    assert parse_rooms("Piso 3 hab. 70 m²") == 3
    assert parse_rooms("2 habitaciones") == 2


def test_extract_habitaclia():
    items = extract_listings(HABITACLIA_HTML, "https://www.habitaclia.com/alquiler-nou_barris-barcelona.htm", "habitaclia")
    assert {i.ext_id for i in items} == {"1234567890123", "9999999999999"}
    a = next(i for i in items if i.ext_id == "1234567890123")
    assert a.price == 1200 and a.rooms == 2 and a.size_m2 == 60
    assert a.url.startswith("https://www.habitaclia.com/alquiler-piso-turo")
    assert a.image == "https://img.example.com/a.jpg"
    b = next(i for i in items if i.ext_id == "9999999999999")
    assert b.price == 783 and b.rooms == 2


def test_extract_idealista():
    html = ('<article><a href="/inmueble/112418418/">Piso en Centre, L\'Hospitalet</a>'
            '<span>850 €/mes</span><span>2 dorm.</span><span>70 m²</span></article>')
    items = extract_listings(html, "https://www.idealista.com/en/alquiler-viviendas/x/", "idealista")
    assert len(items) == 1 and items[0].ext_id == "112418418" and items[0].price == 850 and items[0].rooms == 2


def test_extract_milanuncios():
    html = '<div><a href="/alquiler-de-habitaciones/habitacion-sants-123456789.htm">Habitación en Sants</a> <span>550 €</span> <span>Gastos incluidos, amueblada</span></div>'
    items = extract_listings(html, "https://www.milanuncios.com/x/", "milanuncios")
    assert len(items) == 1 and items[0].price == 550 and items[0].ext_id == "123456789"
