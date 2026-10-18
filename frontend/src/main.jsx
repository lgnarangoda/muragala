import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';
import Bank from './Bank.jsx';
import Phone from './Phone.jsx';
import Guardian from './Guardian.jsx';
import Atm from './Atm.jsx';
import './styles.css';

if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js');
}

const PAGES = { '/bank': Bank, '/phone': Phone, '/guardian': Guardian, '/atm': Atm };
const Page = Object.entries(PAGES).find(([path]) => location.pathname.startsWith(path))?.[1] || App;
ReactDOM.createRoot(document.getElementById('root')).render(<Page />);
