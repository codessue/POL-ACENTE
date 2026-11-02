// Küçük yardımcılar: silme onayı, otomatik gönderim, komisyon hesaplama, plaka büyük harf
document.addEventListener("submit", function (e) {
  var f = e.target;
  if (f.dataset.onay && !confirm(f.dataset.onay)) e.preventDefault();
});
document.addEventListener("change", function (e) {
  var el = e.target;
  if (el.matches("[data-oto-gonder]")) el.form.submit();
  if (el.matches("[data-plaka]")) el.value = el.value.toUpperCase().replace(/\s+/g, "");
  if (el.matches("[data-net]") || el.matches("[data-brut]")) {
    var f = el.form, brut = f.querySelector("[data-brut]"), net = f.querySelector("[data-net]"), kom = f.querySelector("[data-komisyon]");
    var oran = parseFloat((kom && kom.dataset.oran) || "15");
    if (el.matches("[data-brut]") && net && !net.value) net.value = (parseFloat(brut.value || 0) / 1.05).toFixed(2);
    if (kom && !kom.dataset.elle && net.value) kom.value = (parseFloat(net.value || 0) * oran / 100).toFixed(2);
  }
  if (el.matches("[data-komisyon]")) el.dataset.elle = "1";
});
// hesap arama: yazdıkça öneri
document.querySelectorAll("[data-hesap-ara]").forEach(function (inp) {
  var liste = document.getElementById(inp.dataset.hesapAra), gizli = document.querySelector(inp.dataset.hedef);
  var zamanlayici;
  inp.addEventListener("input", function () {
    clearTimeout(zamanlayici);
    var q = inp.value.trim();
    if (q.length < 2) { liste.innerHTML = ""; return; }
    zamanlayici = setTimeout(function () {
      fetch("/api/v1/hesaplar?q=" + encodeURIComponent(q) + "&limit=8").then(function (r) { return r.json(); }).then(function (d) {
        liste.innerHTML = "";
        d.forEach(function (h) {
          var o = document.createElement("option");
          o.value = h.hes_kod + " - " + h.unvan; o.dataset.id = h.id; liste.appendChild(o);
        });
      });
    }, 220);
  });
  inp.addEventListener("change", function () {
    var m = inp.value.match(/^(\S+) - /);
    if (!m) return;
    fetch("/api/v1/hesaplar?q=" + encodeURIComponent(m[1]) + "&limit=1").then(function (r) { return r.json(); }).then(function (d) {
      if (d.length && gizli) gizli.value = d[0].id;
    });
  });
});
