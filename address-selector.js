(() => {
  const email = localStorage.getItem('shopease_user_email');
  const selectorId = 'preferredDeliveryAddress';
  if (document.getElementById(selectorId)) return;

  const topNav = document.querySelector('body > nav')
    || document.querySelector('body > header > nav')
    || document.querySelector('body > header > div');
  if (!topNav) return;

  const bar = document.createElement('section');
  bar.id = selectorId;
  bar.className = 'w-full border-y border-slate-200 bg-slate-50 text-slate-800';
  bar.innerHTML = `
    <div class="mx-auto flex max-w-7xl flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
      <div class="flex min-w-0 flex-1 flex-col gap-1 sm:flex-row sm:items-center sm:gap-3">
        <label for="preferredAddressSelect" class="shrink-0 text-xs font-bold uppercase tracking-wide text-slate-500">Deliver to</label>
        <select id="preferredAddressSelect" aria-label="Choose delivery address" class="w-full min-w-0 rounded-lg border-slate-300 bg-white py-2 pl-3 pr-8 text-sm font-semibold text-slate-800 focus:border-blue-600 focus:ring-blue-600 sm:max-w-2xl"></select>
      </div>
      <a href="profile.html#profile" class="shrink-0 text-sm font-semibold text-blue-800 hover:text-blue-600">Manage addresses</a>
      <p id="addressSelectorMessage" class="sr-only" role="status" aria-live="polite"></p>
    </div>`;
  topNav.insertAdjacentElement('afterend', bar);

  const select = document.getElementById('preferredAddressSelect');
  const message = document.getElementById('addressSelectorMessage');
  const storageKey = email ? `shopease_preferred_address:${email}` : '';

  function addOption(label, value, disabled = false) {
    const option = document.createElement('option');
    option.value = value;
    option.textContent = label;
    option.disabled = disabled;
    select.append(option);
  }

  if (!email) {
    addOption('Sign in to choose a saved address', '', true);
    select.disabled = true;
    message.textContent = 'Sign in to use saved delivery addresses.';
    return;
  }

  addOption('Loading saved addresses...', '', true);
  fetch(`/api/profile?email=${encodeURIComponent(email)}`)
    .then(async response => {
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Unable to load saved addresses');
      const profile = data.profile || {};
      const addresses = profile.addresses?.length ? profile.addresses : (profile.address ? [profile.address] : []);
      select.replaceChildren();
      if (!addresses.length) {
        addOption('No saved addresses yet', '', true);
        message.textContent = 'Add an address in your Profile to choose a delivery destination.';
        return;
      }
      const storedAddress = localStorage.getItem(storageKey);
      const defaultAddress = addresses.includes(storedAddress)
        ? storedAddress
        : (addresses.includes(profile.address) ? profile.address : addresses[0]);
      addresses.forEach((address, index) => {
        const option = document.createElement('option');
        option.value = String(index);
        option.textContent = address;
        option.dataset.address = address;
        option.selected = address === defaultAddress;
        select.append(option);
      });
      localStorage.setItem(storageKey, defaultAddress);
      message.textContent = `Delivering to ${defaultAddress}`;
    })
    .catch(error => {
      select.replaceChildren();
      addOption('Saved addresses unavailable', '', true);
      message.textContent = error.message;
    });

  select.addEventListener('change', () => {
    const address = select.selectedOptions[0]?.dataset.address;
    if (!address) return;
    localStorage.setItem(storageKey, address);
    message.textContent = `Delivering to ${address}`;
    window.dispatchEvent(new CustomEvent('shopease:preferred-address-change', { detail: { address } }));
  });
})();
