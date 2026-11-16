(function () {
  const OCR_SCRIPT_URL = 'https://cdn.jsdelivr.net/npm/tesseract.js@5/dist/tesseract.min.js';
  const TENSORFLOW_SCRIPT_URL = 'https://cdn.jsdelivr.net/npm/@tensorflow/tfjs@4.22.0/dist/tf.min.js';
  const MOBILENET_SCRIPT_URL = 'https://cdn.jsdelivr.net/npm/@tensorflow-models/mobilenet@2.1.1/dist/mobilenet.min.js';
  let ocrScriptPromise;
  let imageModelPromise;

  function loadOcrLibrary() {
    if (window.Tesseract) return Promise.resolve(window.Tesseract);
    if (!ocrScriptPromise) {
      ocrScriptPromise = new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = OCR_SCRIPT_URL;
        script.async = true;
        script.onload = () => {
          if (window.Tesseract) resolve(window.Tesseract);
          else reject(new Error('The text scanner could not be loaded.'));
        };
        script.onerror = () => {
          ocrScriptPromise = null;
          reject(new Error('The text scanner could not be loaded. Check your internet connection and try again.'));
        };
        document.head.appendChild(script);
      });
    }
    return ocrScriptPromise;
  }

  function loadScript(url) {
    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = url;
      script.async = true;
      script.onload = resolve;
      script.onerror = () => reject(new Error('The photo recognition model could not be loaded.'));
      document.head.appendChild(script);
    });
  }

  function loadImageModel() {
    if (window.mobilenet) return Promise.resolve(window.mobilenet.load());
    if (!imageModelPromise) {
      imageModelPromise = (async () => {
        if (!window.tf) await loadScript(TENSORFLOW_SCRIPT_URL);
        if (!window.mobilenet) await loadScript(MOBILENET_SCRIPT_URL);
        if (!window.mobilenet) throw new Error('The photo recognition model could not be loaded.');
        return window.mobilenet.load();
      })().catch(error => {
        imageModelPromise = null;
        throw error;
      });
    }
    return imageModelPromise;
  }

  function normalizeText(value) {
    return value.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim().replace(/\s+/g, ' ');
  }

  function productTokens(name) {
    return normalizeText(name).split(' ')
      .map(token => token.length > 3 && token.endsWith('s') ? token.slice(0, -1) : token)
      .filter(token => token && !['the', 'with', 'smart', 'wireless', 'bluetooth'].includes(token));
  }

  function findProduct(text, products) {
    const normalizedText = normalizeText(text);
    if (!normalizedText) return null;

    const exactMatches = products
      .filter(product => normalizedText.includes(normalizeText(product.name)))
      .sort((first, second) => productTokens(second.name).length - productTokens(first.name).length);
    if (exactMatches.length) return exactMatches[0];

    const normalizedTokens = new Set(normalizedText.split(' ')
      .map(token => token.length > 3 && token.endsWith('s') ? token.slice(0, -1) : token));
    const scored = products.map(product => {
      const tokens = productTokens(product.name);
      const matchedTokens = tokens.filter(token => normalizedTokens.has(token));
      return { product, score: tokens.length ? matchedTokens.length / tokens.length : 0, matched: matchedTokens.length };
    }).filter(result => result.matched >= 2 && result.score >= 0.6)
      .sort((first, second) => second.score - first.score || second.matched - first.matched);

    if (!scored.length) return null;
    if (scored.length > 1 && scored[0].score === scored[1].score && scored[0].matched === scored[1].matched) return null;
    return scored[0].product;
  }

  function categoryForImageLabel(label) {
    const normalizedLabel = normalizeText(label);
    const labelCategories = [
      ['Audio', ['earphone', 'headphone', 'earbud', 'ear electronic equipment', 'loudspeaker', 'speaker', 'stereo', 'microphone']],
      ['Computing', ['laptop', 'notebook computer', 'desktop computer', 'computer monitor']],
      ['Mobiles', ['cellular telephone', 'cell phone', 'smartphone', 'mobile phone']],
      ['Cameras', ['camera', 'digital camera', 'reflex camera', 'webcam']],
      ['Wearables', ['digital watch', 'wristwatch', 'smartwatch']],
      ['Gaming', ['game console', 'joystick', 'game controller']],
      ['Accessories', ['computer mouse', 'computer keyboard', 'mouse', 'keyboard']],
      ['Smart Home', ['home appliance', 'remote control', 'loudspeaker']]
    ];
    const match = labelCategories.find(([, terms]) => terms.some(term => normalizedLabel.includes(term)));
    return match ? match[0] : null;
  }

  async function getClassifierImage(source) {
    if (source instanceof HTMLCanvasElement || source instanceof HTMLImageElement || source instanceof HTMLVideoElement) {
      return source;
    }
    if (!(source instanceof Blob)) throw new Error('This photo format could not be analyzed. Choose a JPG or PNG image.');

    const bitmap = await createImageBitmap(source);
    const canvas = document.createElement('canvas');
    canvas.width = bitmap.width;
    canvas.height = bitmap.height;
    canvas.getContext('2d').drawImage(bitmap, 0, 0);
    bitmap.close();
    return canvas;
  }

  function initialize(options) {
    const button = typeof options.button === 'string' ? document.getElementById(options.button) : options.button;
    if (!button) throw new Error('The camera search button was not found.');

    const products = options.products.map(product => typeof product === 'string' ? { name: product } : product);
    const dialog = document.createElement('dialog');
    dialog.className = 'w-[min(92vw,36rem)] rounded-2xl p-0 text-slate-900 shadow-2xl backdrop:bg-slate-950/70';
    dialog.setAttribute('aria-labelledby', 'productCameraTitle');
    dialog.innerHTML = `
      <div class="p-5 sm:p-6">
        <div class="flex items-start justify-between gap-4">
          <div>
            <h2 id="productCameraTitle" class="text-xl font-bold">Scan a product label</h2>
            <p class="mt-1 text-sm text-slate-600">The scanner can recognize a broad product category from a photo. A readable label is needed to identify an exact model.</p>
          </div>
          <button type="button" data-close class="rounded-lg px-3 py-1 text-2xl leading-none text-slate-500 hover:bg-slate-100" aria-label="Close scanner">&times;</button>
        </div>
        <video class="mt-4 hidden max-h-72 w-full rounded-xl bg-black object-contain" autoplay playsinline muted aria-label="Camera preview"></video>
        <div class="mt-4 flex flex-wrap gap-3">
          <button type="button" data-start class="rounded-lg bg-indigo-600 px-4 py-2 font-semibold text-white hover:bg-indigo-700">Start camera</button>
          <button type="button" data-scan class="hidden rounded-lg bg-blue-600 px-4 py-2 font-semibold text-white hover:bg-blue-700">Scan now</button>
          <label class="cursor-pointer rounded-lg border border-slate-300 px-4 py-2 font-semibold text-slate-700 hover:bg-slate-50">
            Choose a photo
            <input type="file" accept="image/*" capture="environment" class="sr-only" data-file />
          </label>
        </div>
        <p class="mt-4 text-sm text-slate-600" data-status role="status" aria-live="polite">Camera access works on HTTPS or localhost. You can also choose a product photo.</p>
        <p class="mt-2 text-xs text-slate-500">Text is recognized in your browser; product images are not uploaded to ShopEase.</p>
      </div>`;
    document.body.appendChild(dialog);

    const video = dialog.querySelector('video');
    const status = dialog.querySelector('[data-status]');
    const startButton = dialog.querySelector('[data-start]');
    const scanButton = dialog.querySelector('[data-scan]');
    const fileInput = dialog.querySelector('[data-file]');
    let stream = null;
    let scanning = false;

    function stopCamera() {
      if (stream) {
        stream.getTracks().forEach(track => track.stop());
        stream = null;
      }
      video.srcObject = null;
      video.classList.add('hidden');
      scanButton.classList.add('hidden');
      startButton.classList.remove('hidden');
    }

    async function scanImage(image) {
      if (scanning) return;
      scanning = true;
      scanButton.disabled = true;
      startButton.disabled = true;
      fileInput.disabled = true;
      status.textContent = 'Loading text recognition...';
      try {
        const tesseract = await loadOcrLibrary();
        const worker = await tesseract.createWorker('eng', undefined, {
          logger: progress => {
            if (progress.status) {
              const percent = progress.progress ? ` ${Math.round(progress.progress * 100)}%` : '';
              status.textContent = `${progress.status}${percent}`;
            }
          }
        });
        let recognizedText = '';
        try {
          const result = await worker.recognize(image);
          recognizedText = result.data.text || '';
        } finally {
          await worker.terminate();
        }
        const product = findProduct(recognizedText, products);
        if (product) {
          stopCamera();
          dialog.close();
          options.onMatch(product);
          return;
        }

        status.textContent = recognizedText.trim()
          ? 'No product name matched. Checking what kind of product is in the photo...'
          : 'No readable product name found. Checking what kind of product is in the photo...';
        const model = await loadImageModel();
        const classifierImage = await getClassifierImage(image);
        const predictions = await model.classify(classifierImage, 5);
        const categoryPrediction = predictions.find(prediction => categoryForImageLabel(prediction.className));
        const category = categoryPrediction ? categoryForImageLabel(categoryPrediction.className) : null;
        stopCamera();
        dialog.close();
        if (category && products.some(item => item.category === category)) {
          options.onCategoryMatch(category, categoryPrediction.className);
        } else {
          options.onNoMatch(recognizedText, [...new Set(products.map(item => item.category).filter(Boolean))]);
        }
      } catch (error) {
        status.textContent = error.message || 'Could not scan this image. Try a clearer photo.';
      } finally {
        scanning = false;
        scanButton.disabled = false;
        startButton.disabled = false;
        fileInput.disabled = false;
      }
    }

    startButton.addEventListener('click', async () => {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        status.textContent = 'Camera access is unavailable here. Use HTTPS or localhost, or choose a photo instead.';
        return;
      }
      startButton.disabled = true;
      status.textContent = 'Waiting for camera permission...';
      try {
        const cameraStream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: { ideal: 'environment' } },
          audio: false
        });
        if (!dialog.open) {
          cameraStream.getTracks().forEach(track => track.stop());
          return;
        }
        stream = cameraStream;
        video.srcObject = stream;
        video.classList.remove('hidden');
        scanButton.classList.remove('hidden');
        startButton.classList.add('hidden');
        status.textContent = 'Center the product name or model in view, then choose Scan now.';
      } catch (error) {
        status.textContent = error.name === 'NotAllowedError'
          ? 'Camera permission was denied. Allow camera access or choose a photo.'
          : 'Could not start the camera. Choose a photo or check your camera connection.';
      } finally {
        startButton.disabled = false;
      }
    });

    scanButton.addEventListener('click', () => {
      if (!video.videoWidth || !video.videoHeight) {
        status.textContent = 'The camera is not ready yet. Please wait a moment and try again.';
        return;
      }
      const canvas = document.createElement('canvas');
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
      scanImage(canvas);
    });

    fileInput.addEventListener('change', () => {
      const image = fileInput.files && fileInput.files[0];
      if (image) scanImage(image);
      fileInput.value = '';
    });
    dialog.querySelector('[data-close]').addEventListener('click', () => dialog.close());
    dialog.addEventListener('close', stopCamera);
    dialog.addEventListener('click', event => {
      if (event.target === dialog) dialog.close();
    });
    button.addEventListener('click', () => {
      if (!dialog.open) dialog.showModal();
    });
    return {
      open() {
        if (!dialog.open) dialog.showModal();
      }
    };
  }

  window.initializeProductCameraSearch = initialize;
})();
