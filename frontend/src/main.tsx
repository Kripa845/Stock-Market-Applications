import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import './index.css';

// Apply the saved theme before the first render, so pages without the toggle (login, register) match it.
try {
  document.documentElement.setAttribute('data-theme', localStorage.getItem('app-theme') === 'light' ? 'light' : 'dark');
} catch {
  document.documentElement.setAttribute('data-theme', 'dark');
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>
);