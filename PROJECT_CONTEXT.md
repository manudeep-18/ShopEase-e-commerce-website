# ShopEase project context for a research paper

## Project overview

ShopEase is a browser-based electronics e-commerce application. It combines a customer-facing storefront with a Flask API that handles user accounts, saved profile details, shopping carts, wishlists, product ratings, orders, and checkout. The storefront is built from HTML, CSS, and JavaScript. The backend uses MongoDB for application data and integrates Razorpay for prepaid payments; cash on delivery is also supported.

The project is a practical software system, not a deployed commercial store or a completed empirical research study. Product information is maintained in a small, predefined catalogue, and order totals are calculated by the backend. The application includes a camera-assisted product discovery feature: it uses in-browser OCR to look for a product name and, if that does not identify a product, an image classifier to suggest a supported product category. The feature can use a camera or a user-selected image; the code indicates that the image is analyzed in the browser rather than uploaded to ShopEase.

## Suggested research framing

**Working title:** *Design and Implementation of a Web-Based Electronics E-Commerce Platform with Camera-Assisted Product Discovery and Verified Checkout*

This framing describes features that exist in the code and leaves room for a measured evaluation. If the intended paper is specifically about customer segmentation, see **Important scope note** below: the current application stores some customer interactions but does not implement segmentation.

## Research context and problem

Online stores need to support a connected shopping journey—from discovering products to maintaining a cart, completing payment, and tracking an order. This project provides a small-scale implementation of that journey for electronics. It also explores an alternative to text-only discovery: customers can submit a product image, after which browser-side text recognition attempts to match a catalogue item and image classification can fall back to a product category.

The system raises researchable questions about how these functions can be integrated, how accurately and quickly the discovery feature finds useful catalogue results, how checkout correctness can be enforced at the server, and how the end-to-end application behaves in representative user journeys. These are questions for evaluation, not established findings from the repository.

## Aim

To design, implement, and evaluate a prototype e-commerce application that integrates account-scoped shopping functions, camera-assisted product discovery, and server-verified payment and order workflows.

## Possible research questions

1. How accurately does camera-assisted discovery identify an exact catalogue product or a useful product category from representative images?
2. How does the camera-assisted discovery workflow compare with text search in task completion time and successful product discovery?
3. Does server-side validation of catalogue prices, order totals, payment signatures, and captured-payment status prevent invalid or incomplete checkouts in the tested scenarios?
4. Can the application reliably preserve account-specific cart, wishlist, rating, profile, and order data across the tested workflows?

Choose a small number of questions that match the available study time and participants. Questions 1 and 2 require a labeled image set and user or task-based evaluation; questions 3 and 4 can be investigated with systematic integration tests.

## Objectives

- Describe the application architecture and its main customer workflows.
- Document how product discovery combines OCR-based product-name matching with category classification.
- Examine checkout controls, including server-calculated totals, catalogue validation, Razorpay signature and captured-payment checks, and cash-on-delivery order creation.
- Evaluate selected outcomes using reproducible test cases and report the dataset, test environment, metrics, and limitations.
- Identify privacy, reliability, and usability improvements for future work.

## System scope and implementation

### Customer-facing capabilities

- Browse featured and catalogue electronics.
- Search the catalogue and use camera or image-assisted product discovery.
- Create an account, log in, and manage profile and delivery-address details.
- Persist a cart, wishlist, and per-user product ratings.
- Place cash-on-delivery or Razorpay orders.
- Review order history and details, and follow order-status changes, including supported return and refund states.

### Technical design

- **Frontend:** HTML, CSS, and JavaScript pages served by Flask. Tailwind CSS and fonts are loaded from external CDNs.
- **Backend:** Flask JSON endpoints for accounts, profiles, carts, wishlists, ratings, payments, and orders.
- **Database:** MongoDB is the active datastore. A SQLite database is retained as a legacy backup; a migration script copies supported records into MongoDB without modifying the source and is designed to be safe to rerun.
- **Product discovery:** Browser-side Tesseract.js OCR first attempts to match recognized product text against the catalogue. TensorFlow.js with MobileNet is used for category fallback. The implementation uses predefined category mappings and product-token matching.
- **Payment:** The server creates Razorpay orders and verifies the returned signature and payment status before recording a paid order. It also checks the provider-reported amount, currency, and captured status. Card and other payment credentials are handled by Razorpay Checkout rather than stored by ShopEase.
- **Identity and data controls:** The backend uses signed Flask sessions, salted PBKDF2-HMAC-SHA256 password hashes, account-scoped data access, and MongoDB indexes for uniqueness and lookup. These implementation details should not be described as a complete security audit.
- **Testing:** Pytest tests exercise API workflows using `mongomock`, including account isolation, order status changes, payment verification cases, and SQLite migration behavior. Provider interactions are mocked; the tests do not represent live-payment or production-scale evaluation.

## Suggested evaluation methodology

Treat the work as a system design and implementation study with a clearly delimited evaluation, rather than claiming broad real-world effectiveness.

1. **Define the test scope.** Select the workflows and research questions before collecting results. Record the tested software version, browser, operating system, database configuration, and whether external model/CDN downloads are available.
2. **Evaluate image discovery.** Create a documented, consented set of representative product images covering the supported products and categories, plus unrelated or ambiguous images. Label the expected exact product and/or category. Report exact-product match rate, category accuracy, no-match behavior, and latency separately. Include sample counts and describe image conditions.
3. **Compare discovery methods if feasible.** Ask participants to complete equivalent product-finding tasks using text and camera-assisted search. Report task success, completion time, and participant feedback; explain recruitment and consent. Avoid generalizing beyond the sample.
4. **Evaluate backend workflows.** Extend the existing automated tests with explicit expected outcomes for authentication, catalogue-price rejection, tax and delivery calculations, payment verification, order ownership, and order-state transitions. Separate mock-based correctness checks from any live-provider test.
5. **Report limitations.** Discuss catalogue size, model/category coverage, image quality, browser and device variation, network dependence for downloading libraries/models, mocked payment tests, absence of production traffic, and any small or non-representative participant sample.

Do not invent measurements, participant feedback, accuracy scores, performance claims, or deployment results. Fill these in only after conducting and documenting the evaluation.

## Important scope note: customer segmentation

Despite the repository's broader e-commerce/customer-segmentation label, the reviewed application code does **not** implement a customer-segmentation model, recommendation engine, analytics dashboard, or segmentation evaluation. It records user-linked shopping data such as orders, ratings, wishlists, and carts, but this alone is not evidence that customer groups have been computed or validated.

If the intended paper is about customer segmentation, present segmentation as proposed future work unless the project is extended. A defensible study would need a defined and ethically obtained dataset, documented feature engineering, a segmentation method (for example, an explicitly justified clustering approach), baseline or alternative methods, cluster-quality measures, interpretation of segments, and privacy protections. Do not use the retained SQLite backup or real customer records in a paper without confirming authorization, consent/legal basis, and anonymization requirements.

## Limitations and ethical considerations

- The catalogue is predefined and relatively limited; results may not generalize to a large or changing retailer catalogue.
- The image-search pipeline relies on OCR, pretrained image classification, fixed label-to-category mappings, and token matching. Its accuracy and robustness are not established by the code or current tests.
- In-browser analysis avoids sending the selected image to the ShopEase backend according to the implementation, but external scripts and pretrained models are downloaded from CDNs. The paper should accurately describe this distinction and verify actual network behavior in the evaluated environment.
- Automated tests use mocked MongoDB and Razorpay behavior. They demonstrate selected code paths, not production availability, payment-provider performance, or security certification.
- User profile, address, cart, rating, and order information can be sensitive. Use synthetic or properly authorized and de-identified data for research; minimize collected data and report data-handling practices.
- The project is a prototype. Do not imply production readiness, compliance certification, or commercial deployment without independent evidence.

## Short context paragraph for a paper draft

ShopEase is a prototype web-based electronics store developed to integrate product browsing, account-specific shopping functions, product discovery, and checkout in one application. Its frontend uses HTML, CSS, and JavaScript, while a Flask backend exposes JSON APIs and stores application records in MongoDB. In addition to text-based catalogue browsing, the system provides camera-assisted discovery: browser-side OCR attempts to identify a product name, and a pretrained image classifier can provide a category-level fallback. The backend validates checkout items and calculates totals, while prepaid orders are created only after Razorpay signature and captured-payment checks; cash on delivery is also supported. This project provides a basis for studying the implementation and evaluation of an integrated e-commerce workflow. Any conclusions about search accuracy, usability, security, or operational performance must be supported by a documented evaluation; the current code and automated mock-based tests alone do not establish those outcomes.
