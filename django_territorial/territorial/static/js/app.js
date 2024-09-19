import App from './components/App.js';

const { createElement } = React;
const { createRoot } = ReactDOM;

const root = createRoot(document.getElementById('root'));
root.render(createElement(App));
