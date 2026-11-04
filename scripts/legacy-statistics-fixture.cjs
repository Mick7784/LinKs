/* Mount retained report primitives for their component regression suites.
   The current user navigation is exercised by statistics-workspace-browser-test. */
module.exports = async function mountLegacyStatistics(page) {
  await page.evaluate(async () => {
    document.getElementById('statistics-workspace').hidden = true;
    document.getElementById('statistics-legacy').hidden = false;
    document.getElementById('statistics-legacy').style.cssText = 'margin-top:13px;border:1px solid var(--line);border-radius:12px;padding:10px 13px;background:var(--surface)';
    document.getElementById('statistics-filters').append(document.getElementById('analytics-filters'));
    filterAnalysis();
    await loadStats();
  });
};
