import React from 'react';

const Header = React.memo(function Header({ title, subtitle }) {
  return (
    <header>
      <h1>{title}</h1>
      <p>{subtitle}</p>
    </header>
  );
});

export default Header;
