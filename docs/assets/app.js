/* ============================================================================
   GitClaw Terminal UI — Vanilla JavaScript
   Tab switching, expandable rows, live clock, JSON highlighting.
   No frameworks. No build tools. Just raw JS.
   ============================================================================ */

// ── Tab Switching ──────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', function () {
  var tabBtns = document.querySelectorAll('.tab-btn');

  tabBtns.forEach(function (btn) {
    btn.addEventListener('click', function () {
      var tabId = this.getAttribute('data-tab');
      var parent = this.closest('.panel') || document;

      // Deactivate all tabs in this panel
      parent.querySelectorAll('.tab-btn').forEach(function (b) {
        b.classList.remove('active');
      });
      parent.querySelectorAll('.tab-panel').forEach(function (p) {
        p.classList.remove('active');
      });

      // Activate selected
      this.classList.add('active');
      var panel = parent.querySelector('#tab-' + tabId);
      if (panel) panel.classList.add('active');
    });
  });

  // Start the clock
  updateClock();
  setInterval(updateClock, 1000);
});


// ── Expandable Entries ─────────────────────────────────────────────────────

function toggleEntry(header) {
  var body = header.nextElementSibling;
  var icon = header.querySelector('.expand-icon');

  if (!body) return;

  if (body.style.display === 'none' || body.style.display === '') {
    body.style.display = 'block';
    if (icon) icon.textContent = '-';
  } else {
    body.style.display = 'none';
    if (icon) icon.textContent = '+';
  }
}


// ── Live Clock ─────────────────────────────────────────────────────────────

function updateClock() {
  var el = document.getElementById('clock');
  if (!el) return;

  var now = new Date();
  var h = String(now.getUTCHours()).padStart(2, '0');
  var m = String(now.getUTCMinutes()).padStart(2, '0');
  var s = String(now.getUTCSeconds()).padStart(2, '0');
  el.textContent = h + ':' + m + ':' + s + ' UTC';
}


// ── JSON Syntax Highlighting ───────────────────────────────────────────────

function highlightJSON(container) {
  if (!container) return;

  var text = container.textContent;

  // Highlight keys
  text = text.replace(/"([^"]+)":/g, '<span style="color:#ffb300">"$1"</span>:');
  // Highlight string values
  text = text.replace(/:\s*"([^"]*)"/g, ': <span style="color:#00ff41">"$1"</span>');
  // Highlight numbers
  text = text.replace(/:\s*(\d+)/g, ': <span style="color:#00d4ff">$1</span>');
  // Highlight booleans
  text = text.replace(/:\s*(true|false)/g, ': <span style="color:#ff4444">$1</span>');
  // Highlight null
  text = text.replace(/:\s*(null)/g, ': <span style="color:#8b949e">$1</span>');

  container.innerHTML = text;
}

// Auto-highlight JSON views on load
document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('.json-view code').forEach(highlightJSON);
});


// ── Data Refresh ───────────────────────────────────────────────────────────

function fetchData(url, callback) {
  var xhr = new XMLHttpRequest();
  xhr.open('GET', url, true);
  xhr.onreadystatechange = function () {
    if (xhr.readyState === 4 && xhr.status === 200) {
      try {
        var data = JSON.parse(xhr.responseText);
        callback(data);
      } catch (e) {
        // silently fail — data might not exist yet
      }
    }
  };
  xhr.send();
}
