function getCookie(name) {
  const m = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
  return m ? m.pop() : '';
}

function updateCounts(counts) {
  for (const k in counts) {
    const el = document.getElementById('count-' + k);
    if (el) el.textContent = counts[k];
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const slug = document.body.dataset.slug;
  const csrftoken = getCookie('csrftoken');

  document.querySelectorAll('[data-react]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const value = btn.dataset.react;
      const res = await fetch('/api/react/', {
        method: 'POST',
        headers: {
          'X-CSRFToken': csrftoken,
          'Content-Type': 'application/x-www-form-urlencoded'
        },
        body: new URLSearchParams({ slug, value })
      });

      const json = await res.json().catch(() => null);
      if (json && json.ok) {
        updateCounts(json.counts);
      } else {
        console.warn('Reaction failed', json);
      }
    });
  });
});
