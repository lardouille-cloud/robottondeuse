/**
 * Générateur de pages statiques pour chaque robot tondeuse.
 * Lit les données ROBOTS depuis fiche.html et génère un fichier HTML par robot.
 * Objectif SEO : pages statiques indexables par Google.
 */

const fs = require('fs');
const path = require('path');

// ── Extraction du bloc ROBOTS depuis fiche.html ──────────────────────────────
const ficheContent = fs.readFileSync('D:/IA/fiche.html', 'utf8');

const lines = ficheContent.split('\n');
const startLine = lines.findIndex(l => l.startsWith('const ROBOTS = {'));
// find the closing "};" at the start of line (line 1982 = index 1981)
let endLine = -1;
for (let i = startLine + 1; i < lines.length; i++) {
  if (lines[i].startsWith('};') || lines[i] === '};') {
    endLine = i;
    break;
  }
}

const robotsSource = lines.slice(startLine, endLine + 1).join('\n') + '\nmodule.exports = ROBOTS;';
const tmpFile = 'D:/IA/_tmp_robots.js';
fs.writeFileSync(tmpFile, robotsSource, 'utf8');

let ROBOTS;
try {
  ROBOTS = require(tmpFile);
} catch(e) {
  console.error('Erreur lors du chargement des données robots:', e.message);
  process.exit(1);
}

// Cleanup tmp
fs.unlinkSync(tmpFile);

// ── ORDER ────────────────────────────────────────────────────────────────────
const ORDER = ['navimow','ecovacs','dreame','worx','yuka','luba2','husqvarna','mova','a3pro','luba3','boschxs','boschm700','gardenaminimo','gardena750','husqvarna115h','navimow108','stiga1000','kress','honda520','stihl422','ecovacsG1','robomow635','stiga3000','vikingmi632','ecoflowblade','husqvarna430x','ambrogio','luba2_1000','husqvarna450','husqvarna435'];

// ── Utilities ─────────────────────────────────────────────────────────────────
function toSlug(name) {
  return name
    .toLowerCase()
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .replace(/[×]/g, 'x')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

function esc(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g,'&amp;')
    .replace(/</g,'&lt;')
    .replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;')
    .replace(/'/g,'&#39;');
}

function stars(score) {
  const full = Math.floor(score);
  const half = (score - full) >= 0.3 ? 1 : 0;
  const empty = 5 - full - half;
  return '★'.repeat(full) + (half ? '½' : '') + '☆'.repeat(empty);
}

// ── HTML Generator ────────────────────────────────────────────────────────────
function generatePage(robot, slug) {
  const BASE = 'https://tondeuserobotguide.fr';
  const url = `${BASE}/${slug}.html`;
  const titleSEO = `${robot.name} — Avis, Prix, Test 2026 | RoboTondeuse.guide`;
  const descSEO = robot.desc.length > 155
    ? robot.desc.substring(0, 152) + '...'
    : robot.desc;

  const buyButtons = [];
  if (robot.amazon) {
    buyButtons.push(`<a href="${esc(robot.amazon)}" target="_blank" rel="noopener sponsored" class="btn-buy btn-amazon">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 14H9V8h2v8zm4 0h-2V8h2v8z"/></svg>
      Voir sur Amazon
    </a>`);
  }
  if (robot.shop2) {
    buyButtons.push(`<a href="${esc(robot.shop2.url)}" target="_blank" rel="noopener sponsored" class="btn-buy btn-shop2">${esc(robot.shop2.label)} →</a>`);
  }
  if (robot.shop3) {
    buyButtons.push(`<a href="${esc(robot.shop3.url)}" target="_blank" rel="noopener sponsored" class="btn-buy btn-shop3">${esc(robot.shop3.label)} →</a>`);
  }

  const specsHtml = (robot.specs || []).map(s => `
    <div class="spec-item">
      <span class="spec-icon">${s.icon}</span>
      <div class="spec-info">
        <div class="spec-label">${esc(s.label)}</div>
        <div class="spec-value">${esc(s.value)}${s.sub ? `<br/><small>${esc(s.sub)}</small>` : ''}</div>
      </div>
    </div>`).join('');

  const prosHtml = (robot.pros || []).map(p => `<li>${esc(p)}</li>`).join('');
  const consHtml = (robot.cons || []).map(c => `<li>${esc(c)}</li>`).join('');

  const reviewsHtml = (robot.userReviews || []).map(r => `
    <div class="review-card">
      <div class="review-header">
        <span class="review-stars">${'★'.repeat(r.stars)}${'☆'.repeat(5-r.stars)}</span>
        <span class="review-author">${esc(r.author)}</span>
        <span class="review-date">${esc(r.date)}</span>
      </div>
      <p class="review-text">${esc(r.text)}</p>
    </div>`).join('');

  // Related robots (previous/next)
  const idx = ORDER.indexOf(robot.id);
  const prevId = idx > 0 ? ORDER[idx - 1] : null;
  const nextId = idx < ORDER.length - 1 ? ORDER[idx + 1] : null;
  const prevRobot = prevId ? ROBOTS[prevId] : null;
  const nextRobot = nextId ? ROBOTS[nextId] : null;

  const prevSlug = prevRobot ? toSlug(prevRobot.name) : null;
  const nextSlug = nextRobot ? toSlug(nextRobot.name) : null;

  const relatedNav = `
  <div class="related-nav">
    ${prevRobot ? `<a href="${prevSlug}.html" class="related-link">← ${esc(prevRobot.name)}</a>` : '<span></span>'}
    <a href="robots.html" class="related-link related-center">Voir tous les robots</a>
    ${nextRobot ? `<a href="${nextSlug}.html" class="related-link">→ ${esc(nextRobot.name)}</a>` : '<span></span>'}
  </div>`;

  const jsonLdProduct = JSON.stringify({
    "@context": "https://schema.org",
    "@type": "Product",
    "name": robot.name,
    "description": robot.desc,
    "image": `${BASE}/${robot.image}`,
    "brand": {"@type": "Brand", "name": robot.name.split(' ')[0]},
    "offers": {
      "@type": "Offer",
      "price": robot.price.replace(/[^\d,]/g,'').replace(',','.'),
      "priceCurrency": "EUR",
      "availability": robot.amazon ? "https://schema.org/InStock" : "https://schema.org/OutOfStock",
      "url": robot.amazon || url
    },
    "aggregateRating": {
      "@type": "AggregateRating",
      "ratingValue": robot.scoreRaw,
      "bestRating": 5,
      "ratingCount": parseInt((robot.reviews_count || '10').replace(/[^\d]/g, '')) || 10
    }
  });

  const jsonLdBreadcrumb = JSON.stringify({
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    "itemListElement": [
      {"@type":"ListItem","position":1,"name":"Accueil","item":BASE+"/"},
      {"@type":"ListItem","position":2,"name":"Robots 2026","item":BASE+"/robots.html"},
      {"@type":"ListItem","position":3,"name":robot.name,"item":url}
    ]
  });

  return `<!DOCTYPE html>
<html lang="fr">
<head>
<script async src="https://www.googletagmanager.com/gtag/js?id=G-YKQTDKZBC2"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-YKQTDKZBC2');
</script>
<meta charset="UTF-8"/>
<meta http-equiv="X-Frame-Options" content="SAMEORIGIN">
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>${esc(titleSEO)}</title>
<meta name="description" content="${esc(descSEO)}"/>
<link rel="canonical" href="${url}"/>
<meta property="og:type" content="product"/>
<meta property="og:url" content="${url}"/>
<meta property="og:title" content="${esc(robot.name)} — Avis &amp; Test 2026"/>
<meta property="og:description" content="${esc(descSEO)}"/>
<meta property="og:image" content="${BASE}/${esc(robot.image)}"/>
<meta property="og:locale" content="fr_FR"/>
<meta name="twitter:card" content="summary_large_image"/>
<script type="application/ld+json">${jsonLdProduct}</script>
<script type="application/ld+json">${jsonLdBreadcrumb}</script>
<link href="fonts/inter.css" rel="stylesheet"/>
<link rel="stylesheet" href="style.css"/>
<style>
.fiche-hero{padding:100px 5% 48px;display:flex;align-items:center;gap:40px;flex-wrap:wrap;}
.fiche-img-wrap{flex:0 0 260px;display:flex;align-items:center;justify-content:center;border-radius:16px;padding:32px;min-height:220px;background:${robot.imgBg || 'var(--card)'};}
.fiche-img-wrap img{max-width:200px;max-height:180px;object-fit:contain;}
.fiche-meta{flex:1;min-width:260px;}
.fiche-tag{display:inline-block;padding:4px 12px;border-radius:20px;font-size:.75rem;font-weight:600;margin-bottom:12px;
  color:${robot.tagColor||'#86efac'};background:${robot.tagBg||'rgba(134,239,172,0.12)'};border:1px solid ${robot.tagBorder||'rgba(134,239,172,0.3)'};}
.fiche-name{font-size:2rem;font-weight:800;line-height:1.2;margin-bottom:8px;}
.fiche-score{font-size:1.1rem;margin-bottom:4px;color:var(--green-l);}
.fiche-price{font-size:1.6rem;font-weight:700;color:#fff;margin-bottom:16px;}
.fiche-desc{color:var(--muted);line-height:1.7;margin-bottom:20px;font-size:.95rem;}
.buy-buttons{display:flex;gap:12px;flex-wrap:wrap;}
.btn-buy{padding:12px 22px;border-radius:8px;font-weight:600;font-size:.9rem;text-decoration:none;display:inline-flex;align-items:center;gap:8px;transition:opacity .2s;}
.btn-amazon{background:#f90;color:#000;}
.btn-shop2,.btn-shop3{background:var(--card);color:var(--fg);border:1px solid var(--border);}
.btn-buy:hover{opacity:.85;}
.section-pad{padding:48px 5%;}
.specs-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:16px;margin-top:24px;}
.spec-item{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:16px;display:flex;align-items:flex-start;gap:12px;}
.spec-icon{font-size:1.3rem;flex-shrink:0;}
.spec-label{font-size:.72rem;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);margin-bottom:2px;}
.spec-value{font-weight:600;font-size:.92rem;}
.spec-value small{font-weight:400;color:var(--muted);font-size:.8rem;}
.proscons{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin-top:24px;}
.pros-box,.cons-box{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:20px;}
.pros-box{border-left:3px solid #22c55e;}
.cons-box{border-left:3px solid #ef4444;}
.pros-box h3{color:#22c55e;font-size:.85rem;text-transform:uppercase;letter-spacing:.08em;margin-bottom:12px;}
.cons-box h3{color:#ef4444;font-size:.85rem;text-transform:uppercase;letter-spacing:.08em;margin-bottom:12px;}
.pros-box ul,.cons-box ul{list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:8px;}
.pros-box li::before{content:'✓ ';color:#22c55e;font-weight:700;}
.cons-box li::before{content:'✗ ';color:#ef4444;font-weight:700;}
.verdict-box{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:24px;margin-top:24px;border-left:3px solid var(--green-l);}
.verdict-text{font-style:italic;font-size:1rem;line-height:1.7;color:var(--fg);margin-bottom:8px;}
.verdict-src{font-size:.8rem;color:var(--muted);}
.reviews-list{display:flex;flex-direction:column;gap:16px;margin-top:24px;}
.review-card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:20px;}
.review-header{display:flex;align-items:center;gap:12px;margin-bottom:10px;flex-wrap:wrap;}
.review-stars{color:#fbbf24;font-size:1rem;}
.review-author{font-weight:600;font-size:.9rem;}
.review-date{color:var(--muted);font-size:.8rem;}
.review-text{color:var(--muted);line-height:1.6;font-size:.9rem;margin:0;}
.cta-section{background:linear-gradient(135deg,rgba(22,163,74,.08),rgba(14,165,233,.06));border:1px solid rgba(22,163,74,.2);border-radius:16px;padding:32px;text-align:center;margin:48px 5%;}
.cta-section h3{font-size:1.2rem;margin-bottom:8px;}
.cta-section p{color:var(--muted);margin-bottom:20px;font-size:.9rem;}
.cta-btns{display:flex;gap:12px;justify-content:center;flex-wrap:wrap;}
.cta-btn{padding:12px 24px;border-radius:8px;font-weight:600;font-size:.9rem;text-decoration:none;}
.cta-btn-primary{background:var(--green);color:#fff;}
.cta-btn-secondary{background:var(--card);color:var(--fg);border:1px solid var(--border);}
.breadcrumb{padding:20px 5% 0;font-size:.8rem;color:var(--muted);}
.breadcrumb a{color:var(--muted);text-decoration:none;}
.breadcrumb a:hover{color:var(--green-l);}
.breadcrumb span{margin:0 6px;opacity:.4;}
.related-nav{display:flex;justify-content:space-between;align-items:center;padding:24px 5%;gap:16px;border-top:1px solid var(--border);flex-wrap:wrap;}
.related-link{color:var(--muted);text-decoration:none;font-size:.85rem;padding:8px 14px;border:1px solid var(--border);border-radius:8px;transition:all .2s;}
.related-link:hover{color:var(--green-l);border-color:rgba(34,197,94,.3);}
.related-center{background:var(--green);color:#fff;border-color:transparent;}
.related-center:hover{opacity:.85;color:#fff;}
@media(max-width:640px){
  .fiche-hero{padding:80px 5% 32px;}
  .proscons{grid-template-columns:1fr;}
  .fiche-name{font-size:1.5rem;}
}
</style>
</head>
<body>
<nav id="nav">
  <a href="index.html" class="nav-logo">
    <svg class="logo-icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="12" cy="12" r="9.5" stroke="currentColor" stroke-width="1.2" opacity="0.35"/>
      <path d="M4 15 Q12 3.5 20 15" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
      <path d="M15.5 4 Q4 12 15.5 20" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
      <circle cx="12" cy="12" r="2.2" fill="currentColor"/>
    </svg>
    <span class="logo-name">Robot<em>Tondeuse</em><s>.guide</s></span>
  </a>
  <div class="nav-links">
    <a href="index.html">Accueil</a>
    <a href="quiz.html">Mon robot idéal</a>
    <a href="robots.html" class="nav-active">Robots 2026</a>
    <a href="comparatif.html">Vue d'ensemble</a>
  </div>
  <a class="nav-premium-btn" href="robots.html">Voir les 30 robots →</a>
</nav>

<div class="breadcrumb">
  <a href="index.html">Accueil</a>
  <span>›</span>
  <a href="robots.html">Robots 2026</a>
  <span>›</span>
  ${esc(robot.name)}
</div>

<section class="fiche-hero">
  <div class="fiche-img-wrap">
    <img src="${esc(robot.image)}" alt="${esc(robot.name)} — robot tondeuse" width="200" height="180" onerror="this.style.display='none'"/>
  </div>
  <div class="fiche-meta">
    <div class="fiche-tag">${esc(robot.tag)}</div>
    <h1 class="fiche-name">${esc(robot.name)}</h1>
    <div class="fiche-score">${stars(robot.scoreRaw)} ${esc(robot.score)} · ${esc(robot.reviews_count)}</div>
    <div class="fiche-price">${esc(robot.price)}${robot.priceNote ? `<small style="font-size:.75rem;font-weight:400;color:var(--muted);margin-left:8px;">${esc(robot.priceNote)}</small>` : ''}</div>
    <p class="fiche-desc">${esc(robot.desc)}</p>
    <div class="buy-buttons">
      ${buyButtons.join('\n      ')}
    </div>
  </div>
</section>

<section class="section-pad" style="background:var(--dark);">
  <div class="section-label">Caractéristiques</div>
  <h2 class="section-title" style="font-size:1.3rem;">Fiche technique</h2>
  <div class="specs-grid">${specsHtml}</div>
</section>

<section class="section-pad">
  <div class="section-label">Notre analyse</div>
  <h2 class="section-title" style="font-size:1.3rem;">Points forts &amp; limites</h2>
  <div class="proscons">
    <div class="pros-box">
      <h3>Points forts</h3>
      <ul>${prosHtml}</ul>
    </div>
    <div class="cons-box">
      <h3>Limites</h3>
      <ul>${consHtml}</ul>
    </div>
  </div>
  ${robot.verdict ? `<div class="verdict-box">
    <p class="verdict-text">${esc(robot.verdict)}</p>
    <div class="verdict-src">${esc(robot.verdictSource || '')}</div>
  </div>` : ''}
</section>

<section class="section-pad" style="background:var(--dark);">
  <div class="section-label">Ce qu'en pensent les acheteurs</div>
  <h2 class="section-title" style="font-size:1.3rem;">Avis vérifiés</h2>
  <div class="reviews-list">${reviewsHtml}</div>
</section>

<div class="cta-section">
  <h3>Pas sûr que le ${esc(robot.name)} soit fait pour vous ?</h3>
  <p>Répondez à 3 questions et obtenez votre sélection personnalisée parmi 30 robots.</p>
  <div class="cta-btns">
    <a href="quiz.html" class="cta-btn cta-btn-primary">Trouver mon robot idéal →</a>
    <a href="comparatif.html" class="cta-btn cta-btn-secondary">Comparer tous les robots</a>
  </div>
</div>

${relatedNav}

<footer>
  <div class="footer-brand">
    <a href="index.html" class="footer-logo-link">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" style="color:var(--green-l)">
        <circle cx="12" cy="12" r="9.5" stroke="currentColor" stroke-width="1.2" opacity="0.35"/>
        <path d="M4 15 Q12 3.5 20 15" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
        <path d="M15.5 4 Q4 12 15.5 20" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
        <circle cx="12" cy="12" r="2.2" fill="currentColor"/>
      </svg>
      <span class="footer-logo">Robot<span>Tondeuse</span>.guide</span>
    </a>
    <p style="color:var(--muted);font-size:.78rem;margin-top:8px;line-height:1.6;">Guide indépendant · Non affilié aux marques citées<br/>Mis à jour mars 2026</p>
  </div>
  <div class="footer-links-col">
    <div class="footer-col-title">Navigation</div>
    <a href="robots.html">Robots 2026</a>
    <a href="comparatif.html">Tableau comparatif</a>
    <a href="quiz.html">Configurateur</a>
    <a href="index.html#conseils">Conseils d'achat</a>
  </div>
  <div class="footer-links-col">
    <div class="footer-col-title">Guides</div>
    <a href="robot-tondeuse-sans-fil.html">Sans fil périmètre</a>
    <a href="robot-tondeuse-pente.html">Terrain en pente</a>
    <a href="robot-tondeuse-petit-jardin.html">Petit jardin</a>
  </div>
  <div class="footer-links-col">
    <div class="footer-col-title">Outils</div>
    <a href="simulateur.html">Simulateur coût 3 ans</a>
    <a href="comparateur.html">Comparateur côte à côte</a>
    <a href="checklist.html">Checklist jardin</a>
  </div>
</footer>
</body>
</html>`;
}

// ── Génération des pages ──────────────────────────────────────────────────────
const generated = [];
const slugMap = {};

for (const id of ORDER) {
  const robot = ROBOTS[id];
  if (!robot) { console.warn(`Robot introuvable: ${id}`); continue; }

  const slug = toSlug(robot.name);
  slugMap[id] = slug;
  const outFile = `D:/IA/${slug}.html`;
  const html = generatePage(robot, slug);
  fs.writeFileSync(outFile, html, 'utf8');
  generated.push({ id, slug, name: robot.name, file: `${slug}.html`, price: robot.price });
  console.log(`✓ ${slug}.html`);
}

// ── Mise à jour du sitemap ────────────────────────────────────────────────────
const BASE = 'https://tondeuserobotguide.fr';
const today = '2026-03-17';

let sitemap = fs.readFileSync('D:/IA/sitemap.xml', 'utf8');

// Remove old fiche.html?id=... entries
sitemap = sitemap.replace(/\s*<!-- Fiches produits individuelles[^>]*>[\s\S]*?<\/urlset>/, '\n</urlset>');

// Add static fiche entries before </urlset>
const ficheEntries = generated.map(r => `
  <url>
    <loc>${BASE}/${r.slug}.html</loc>
    <lastmod>${today}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.85</priority>
  </url>`).join('');

sitemap = sitemap.replace('</urlset>', `
  <!-- Fiches produits statiques — 30 robots -->
${ficheEntries}

</urlset>`);

fs.writeFileSync('D:/IA/sitemap.xml', sitemap, 'utf8');
console.log(`\n✓ sitemap.xml mis à jour avec ${generated.length} fiches statiques`);

// ── Rapport ───────────────────────────────────────────────────────────────────
console.log(`\n── Résumé ──────────────────────────────────`);
console.log(`${generated.length} pages générées`);
generated.forEach(r => console.log(`  ${r.file}  (${r.name}  ${r.price})`));
