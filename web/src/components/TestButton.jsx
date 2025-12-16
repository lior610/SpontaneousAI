export const TestButton = ({ onClick, disabled, label, description }) => {
  return (
    <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
      <button onClick={onClick} disabled={disabled}>
        {label}
      </button>
      <span style={{ fontSize: '14px', color: '#666' }}>
        {description}
      </span>
    </div>
  );
};

