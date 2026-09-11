const form = document.querySelector('#callback-form');
const button = document.querySelector('#submit-button');
const message = document.querySelector('#form-message');

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  message.textContent = '';
  const name = form.elements.name.value.trim();
  const phone = form.elements.phone.value.replace(/\D/g, '').replace(/^91(?=\d{10}$)/, '');
  if (!name) return show('Please enter your name.', true);
  if (!/^[6-9]\d{9}$/.test(phone)) return show('Enter a valid 10-digit Indian mobile number.', true);

  button.disabled = true;
  button.textContent = 'Starting your callback…';
  try {
    const response = await fetch('/api/request-callback', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({name, phone, website: form.elements.website.value})
    });
    const data = await response.json();
    show(data.message || 'Something went wrong. Please try again.', !response.ok);
    if (response.ok) form.reset();
  } catch {
    show('Unable to reach the callback service. Please try again.', true);
  } finally {
    button.disabled = false;
    button.innerHTML = 'Call me now <span aria-hidden="true">→</span>';
  }
});
function show(text, error) { message.textContent = text; message.className = `message ${error ? 'error' : 'success'}`; }
