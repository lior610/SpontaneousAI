export const StatusDisplay = ({ status }) => {
  if (!status) return null;

  return (
    <div style={{ 
      padding: '15px', 
      backgroundColor: status.success ? '#d4edda' : '#f8d7da',
      border: `1px solid ${status.success ? '#c3e6cb' : '#f5c6cb'}`,
      borderRadius: '5px',
      marginTop: '20px'
    }}>
      <h3>{status.success ? 'Success' : 'Error'}</h3>
      <pre style={{ whiteSpace: 'pre-wrap' }}>
        {JSON.stringify(status.data || { error: status.error, details: status.details }, null, 2)}
      </pre>
    </div>
  );
};

