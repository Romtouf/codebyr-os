/* Codebyr OS — Bouclier anti-hameçonnage (content script).
 * Compare le domaine visité aux domaines de banque protégés (injectés par
 * codebyr-space). Si le site RESSEMBLE à une banque sans être son domaine
 * officiel, il barre la page d'un avertissement. */
(function () {
    "use strict";
    var PROTEGES = [/*__DOMAINES__*/];
    if (!PROTEGES.length)
        return;

    function coeur(d) {
        d = (d || "").toLowerCase().replace(/^www\./, "");
        var parts = d.split(".");
        return parts.length > 1 ? parts.slice(0, -1).join(".") : d;
    }

    function leven(a, b) {
        var m = a.length, n = b.length, i, j;
        var dp = [];
        for (i = 0; i <= m; i++) { dp[i] = [i]; }
        for (j = 0; j <= n; j++) { dp[0][j] = j; }
        for (i = 1; i <= m; i++) {
            for (j = 1; j <= n; j++) {
                dp[i][j] = Math.min(
                    dp[i - 1][j] + 1,
                    dp[i][j - 1] + 1,
                    dp[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
            }
        }
        return dp[m][n];
    }

    var host = (location.hostname || "").toLowerCase();
    var banque = null;
    for (var k = 0; k < PROTEGES.length; k++) {
        var p = PROTEGES[k].toLowerCase();
        // Domaine officiel exact (ou sous-domaine) : ce n'est PAS un imposteur.
        if (host === p || host.endsWith("." + p)) { banque = null; break; }
        var cp = coeur(p), ch = coeur(host);
        if (!cp || cp.length < 3) continue;
        if (ch === cp) { banque = p; break; }                       // même cœur, autre extension
        var d = leven(ch, cp);
        if (d > 0 && d <= 2 && Math.abs(ch.length - cp.length) <= 2) { banque = p; break; }
        if (cp.length >= 4 && host.indexOf(cp) !== -1) { banque = p; break; } // cœur inséré
    }
    if (!banque)
        return;

    function afficher() {
        if (document.getElementById("codebyr-antiphishing"))
            return;
        var o = document.createElement("div");
        o.id = "codebyr-antiphishing";
        o.setAttribute("style",
            "position:fixed;inset:0;z-index:2147483647;background:#7f1d1d;color:#fff;" +
            "display:flex;align-items:center;justify-content:center;padding:24px;" +
            "font-family:system-ui,sans-serif;");
        o.innerHTML =
            '<div style="max-width:560px;text-align:center;">' +
            '<div style="font-size:60px;line-height:1;">⚠️</div>' +
            '<h1 style="font-size:26px;margin:14px 0 8px;">Attention — site suspect</h1>' +
            '<p style="font-size:17px;line-height:1.6;">Ce site (<b>' + host + '</b>) ressemble ' +
            'au site de votre banque (<b>' + banque + '</b>) mais ce n\'en est <b>pas</b> ' +
            'le site officiel.<br><br>N\'entrez <b>jamais</b> vos identifiants ici. Pour votre ' +
            'banque, utilisez l\'Espace <b>Banque</b> de Codebyr OS.</p>' +
            '<button id="codebyr-ap-close" style="margin-top:16px;padding:11px 22px;font-size:15px;' +
            'border:0;border-radius:10px;background:#fff;color:#7f1d1d;font-weight:700;cursor:pointer;">' +
            'Quitter ce site</button>' +
            '<div style="margin-top:18px;opacity:.75;font-size:13px;">Protection Codebyr OS</div>' +
            '</div>';
        (document.body || document.documentElement).appendChild(o);
        var b = document.getElementById("codebyr-ap-close");
        if (b) b.addEventListener("click", function () { location.href = "about:blank"; });
    }

    if (document.body) afficher();
    document.addEventListener("DOMContentLoaded", afficher);
    var iv = setInterval(function () {
        if (document.body) { afficher(); clearInterval(iv); }
    }, 40);
    setTimeout(function () { clearInterval(iv); }, 6000);
})();
