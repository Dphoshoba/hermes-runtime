import React, { forwardRef } from 'react';

const ForwardRefComponent = forwardRef(function ForwardRefComponent(props, ref) {
  return (
    <input ref={ref} {...props} />
  );
});

export default ForwardRefComponent;
