import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';
import Bank from './Bank.jsx';
import './styles.css';

if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js');
}

const Page = location.pathname.startsWith('/bank') ? Bank : App;
ReactDOM.createRoot(document.getElementById('root')).render(<Page />);
