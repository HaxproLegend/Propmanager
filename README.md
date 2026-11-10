# PropManager

Front-end-only property maintenance demo based on the submitted PRD v1.2. Built with HTML5, CSS3 and vanilla JavaScript modules; no backend or framework.

## Run in VS Code

Install the recommended Live Server extension, open this folder in VS Code and use **Open with Live Server** on `index.html`. IndexedDB and localStorage require a local web origin, so do not open the HTML file directly from Finder.

## Week 1 foundation

- `index.html` is the single-page app shell.
- `css/` contains base, layout and component styles.
- `js/db.js` owns IndexedDB setup and shared database requests.
- `js/seed.js` seeds the first run with 2 properties, 8 units, 6 tenants and 6 sample tickets.
- `js/state.js` stores the active role under `propmanager.role`.
- `js/views/` contains the navigation, form, board and property directory views.

The app data is stored in the `propmanager-db` database (version 1). All records are sample data. The role toggle is a demo control, not authentication.
