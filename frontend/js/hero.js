/*
 * Vanilla-JS port of the ScrollExpandMedia component.
 * Hijacks wheel + touch until the media frame reaches full size,
 * then releases control to normal page scrolling.
 */

(function () {
  const root       = document.querySelector('.hero-root');
  if (!root) return;

  const media      = document.getElementById('hero-media');
  const titleLeft  = document.getElementById('hero-title-left');
  const titleRight = document.getElementById('hero-title-right');
  const subline    = document.getElementById('hero-subline');
  const bg         = document.getElementById('hero-bg');
  const content    = document.getElementById('hero-content');

  let progress          = 0;    // 0 → 1
  let fullyExpanded     = false;
  let touchStartY       = 0;

  const isMobile = () => window.innerWidth < 768;

  document.body.classList.add('hero-locked');

  function apply() {
    const m         = isMobile();
    const width     = 300 + progress * (m ? 620 : 1220);
    const height    = 400 + progress * (m ? 180 : 380);
    const textShift = progress * (m ? 16 : 14);   // vw

    media.style.width  = `${width}px`;
    media.style.height = `${height}px`;

    titleLeft.style.transform  = `translateX(-${textShift}vw)`;
    titleRight.style.transform = `translateX(${textShift}vw)`;
    subline.style.transform    = `translateX(${textShift * 0.6}vw)`;

    bg.style.opacity = String(1 - progress);

    if (progress >= 1 && !fullyExpanded) {
      fullyExpanded = true;
      content.classList.add('visible');
      document.body.classList.remove('hero-locked');
    } else if (progress < 0.75 && fullyExpanded) {
      fullyExpanded = false;
      content.classList.remove('visible');
      document.body.classList.add('hero-locked');
    }
  }

  function step(delta) {
    progress = Math.min(Math.max(progress + delta, 0), 1);
    apply();
  }

  // ── Wheel ─────────────────────────────────────────────────────
  window.addEventListener('wheel', (e) => {
    if (fullyExpanded && e.deltaY < 0 && window.scrollY <= 4) {
      fullyExpanded = false;
      document.body.classList.add('hero-locked');
      e.preventDefault();
      return;
    }
    if (!fullyExpanded) {
      e.preventDefault();
      step(e.deltaY * 0.0009);
    }
  }, { passive: false });

  // ── Touch ─────────────────────────────────────────────────────
  window.addEventListener('touchstart', (e) => {
    touchStartY = e.touches[0].clientY;
  }, { passive: false });

  window.addEventListener('touchmove', (e) => {
    if (!touchStartY) return;
    const deltaY = touchStartY - e.touches[0].clientY;

    if (fullyExpanded && deltaY < -20 && window.scrollY <= 4) {
      fullyExpanded = false;
      document.body.classList.add('hero-locked');
      e.preventDefault();
      return;
    }
    if (!fullyExpanded) {
      e.preventDefault();
      const factor = deltaY < 0 ? 0.008 : 0.005;
      step(deltaY * factor);
      touchStartY = e.touches[0].clientY;
    }
  }, { passive: false });

  window.addEventListener('touchend', () => { touchStartY = 0; });

  // ── Keep body at top while locked ─────────────────────────────
  window.addEventListener('scroll', () => {
    if (!fullyExpanded) window.scrollTo(0, 0);
  });

  window.addEventListener('resize', apply);
  apply();
})();
