import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Route, Routes } from 'react-router-dom';
import { fetchData } from '../api';
import { useCustomHook } from '../hooks/useCustomHook';

function App() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const customValue = useCustomHook();

  useEffect(() => {
    fetchData().then(result => {
      setData(result);
      setLoading(false);
    });
  }, []);

  if (loading) return <div>Loading...</div>;

  return (
    <Router>
      <div className="app">
        <h1>Test App</h1>
        <Routes>
          <Route path="/" element={<Home data={data} />} />
          <Route path="/about" element={<About />} />
        </Routes>
      </div>
    </Router>
  );
}

function Home({ data }) {
  return (
    <div>
      <h2>Home</h2>
      <p>{data.message}</p>
    </div>
  );
}

function About() {
  return (
    <div>
      <h2>About</h2>
    </div>
  );
}

export default App;
