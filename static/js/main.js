document.addEventListener('DOMContentLoaded', function() {
  // File upload validation
  const fileInput = document.getElementById('manifest');
  const uploadBtn = document.getElementById('uploadBtn');
  const processBtn = document.getElementById('processBtn');

  if (fileInput && uploadBtn) {
    fileInput.addEventListener('change', function(e) {
      const file = e.target.files[0];
      if (file) {
        const fileSize = file.size / 1024 / 1024; // MB
        const fileName = file.name.toLowerCase();
        if (fileSize > 10) {
          showAlert('File size must be less than 10MB', 'error');
          fileInput.value = '';
          return;
        }
        const validExtensions = ['.xls', '.xlsx', '.csv'];
        if (!validExtensions.some(ext => fileName.endsWith(ext))) {
          showAlert('Please select a valid Excel or CSV file', 'error');
          fileInput.value = '';
          return;
        }
        console.log('File selected:', `${file.name} (${fileSize.toFixed(2)} MB)`);
      }
    });

    const uploadForm = document.getElementById('uploadForm');
    if (uploadForm) {
      uploadForm.addEventListener('submit', function(e) {
        if (!fileInput.files[0]) {
          e.preventDefault();
          showAlert('Please select a file first', 'error');
          return;
        }
        uploadBtn.disabled = true;
        uploadBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Uploading...';
      });
    }
  }

  if (processBtn) {
    const form = processBtn.closest('form');
    form.addEventListener('submit', function(e) {
      const required = ['Product Name','Quantity','Orig. Retail'];
      const missing = [];
      required.forEach(field => {
        const sel = document.querySelector(`select[name="${field}"]`);
        if (!sel.value) missing.push(field);
      });
      if (missing.length) {
        e.preventDefault();
        showAlert(`Please map the required fields: ${missing.join(', ')}`, 'error');
        return;
      }
      processBtn.disabled = true;
      processBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Processing...';
      showAlert('Processing manifest and fetching eBay prices...', 'info');
    });
  }

  // auto‐map on load
  if (document.querySelector('select[name="Product Name"]')) {
    autoMapColumns();
  }

  // auto-dismiss any existing alerts
  document.querySelectorAll('.alert').forEach(alert => {
    if (alert.querySelector('.btn-close')) {
      setTimeout(() => alert.remove(), 5000);
    }
  });
});

// Utility: show Bootstrap-style alerts
function showAlert(message, type='info') {
  const container = document.querySelector('.container') || document.body;
  const div = document.createElement('div');
  div.className = `alert alert-${type==='error'?'danger':type} alert-dismissible fade show`;
  div.innerHTML = `
    <i class="fas fa-${type==='error'?'exclamation-triangle':'info-circle'} me-2"></i>
    ${message}
    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
  `;
  container.prepend(div);
  setTimeout(() => div.remove(), 5000);
}

// Core auto-mapping logic
function autoMapColumns() {
  const mappings = {
    'Product Name':    ['product_name','product','item_name','item','name','description'],
    'Quantity':        ['quantity','qty','amount','count','units'],
    'Orig. Retail':    ['price','retail','retail_price','original_price','value','msrp'],
    'UPC':             ['upc','barcode','ean','gtin'],
    'ASIN':            ['asin','amazon','amazon_id'],
    'Category':        ['category','cat','type','department','section'],
    'Listing ID':      ['listing_id','id','sku','item_id','product_id'],
    'Listing Title': ['listing title','listing_title','listing name','ad_title','posting_title','title','title_col'],
    'Stock Image':     ['stock_image','image','photo','image_url','origin_image','origin_photo'],
    'Cost per Unit':   ['cost_per_unit','unit_cost','cost per unit','cost']
  };

  Object.entries(mappings).forEach(([field, patterns]) => {
    const sel = document.querySelector(`select[name="${field}"]`);
    if (!sel || sel.value) return;
    for (const opt of sel.options) {
      const txt = opt.text.toLowerCase();
      if (patterns.some(pat => txt.includes(pat))) {
        sel.value = opt.value;
        sel.dispatchEvent(new Event('change'));
        break;
      }
    }
  });
}

// Clipboard helper
function copyToClipboard(text) {
  if (navigator.clipboard) {
    navigator.clipboard.writeText(text)
      .then(() => showAlert('Link copied!', 'success'))
      .catch(() => fallbackCopy(text));
  } else fallbackCopy(text);
}
function fallbackCopy(text) {
  const ta = document.createElement('textarea');
  ta.value = text;
  document.body.appendChild(ta);
  ta.select();
  try { document.execCommand('copy'); showAlert('Link copied!', 'success'); }
  catch { showAlert('Copy failed', 'error'); }
  document.body.removeChild(ta);
}

// Optional: form validation utility
function validateForm(form) {
  let ok = true;
  form.querySelectorAll('[required]').forEach(inp => {
    if (!inp.value.trim()) {
      inp.classList.add('is-invalid');
      ok = false;
    } else inp.classList.remove('is-invalid');
  });
  return ok;
}

// Progress overlay (if you choose to call it)
function showProgress(msg) {
  hideProgress();
  const div = document.createElement('div');
  div.className = 'progress-container position-fixed top-50 start-50 translate-middle';
  div.innerHTML = `
    <div class="card shadow">
      <div class="card-body text-center">
        <div class="spinner-border mb-3" role="status"><span class="visually-hidden">Loading...</span></div>
        <div>${msg}</div>
      </div>
    </div>
  `;
  document.body.append(div);
}
function hideProgress() {
  document.querySelectorAll('.progress-container').forEach(el => el.remove());
}
