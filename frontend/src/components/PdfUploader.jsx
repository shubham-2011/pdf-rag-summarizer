import React, { useState, useRef } from 'react';
import { uploadPdfApi } from '../api/client';
import { Upload, FileText, CheckCircle, AlertOctagon, Loader, ExternalLink } from 'lucide-react';

export default function PdfUploader({ apiKey, onPdfUploaded }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [fileInfo, setFileInfo] = useState(null);
  const fileInputRef = useRef(null);

  const handleFileChange = async (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;

    const allowedExtensions = ['.pdf', '.docx', '.doc', '.pptx', '.ppt'];
    const hasValidExt = allowedExtensions.some(ext => file.name.toLowerCase().endsWith(ext));
    if (!hasValidExt) {
      setError('Document Cannot Be Embedded: Only PDF, Word (.docx, .doc), and PowerPoint (.pptx, .ppt) documents are supported.');
      return;
    }

    // Client-side file size pre-audit (50MB limit)
    const maxSizeBytes = 50 * 1024 * 1024;
    if (file.size > maxSizeBytes) {
      const fileSizeMb = (file.size / (1024 * 1024)).toFixed(2);
      setError(`Document Cannot Be Embedded: File size (${fileSizeMb} MB) exceeds maximum allowed limit of 50 MB.`);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const data = await uploadPdfApi(file, apiKey);
      setFileInfo(data);
      if (onPdfUploaded) {
        onPdfUploaded(data);
      }
    } catch (err) {
      console.error("Upload error:", err);
      setError(err.response?.data?.detail || err.message || 'PDF Cannot Be Embedded: Upload or parsing failed.');
    } finally {
      setLoading(false);
    }
  };

  const handleBoxClick = () => {
    if (fileInputRef.current && !loading) {
      fileInputRef.current.click();
    }
  };

  return (
    <div className="card">
      <div 
        className="dropzone" 
        onClick={handleBoxClick} 
        style={{ cursor: 'pointer', touchAction: 'manipulation', padding: '2.5rem 1rem' }}
      >
        <input 
          ref={fileInputRef}
          type="file" 
          accept=".pdf,.docx,.doc,.pptx,.ppt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.presentationml.presentation" 
          onChange={handleFileChange} 
          id="pdf-input" 
          style={{ display: 'none' }} 
        />
        {loading ? (
          <div>
            <Loader className="animate-spin" size={44} style={{ color: '#6366f1', margin: '0 auto 1rem' }} />
            <h3 style={{ fontSize: '1.1rem' }}>Auditing & Embedding Document...</h3>
            <p style={{ color: '#94a3b8', fontSize: '0.9rem' }}>Validating text extractability and indexing into Vector Store...</p>
          </div>
        ) : (
          <div>
            <Upload size={44} style={{ color: '#6366f1', margin: '0 auto 1rem' }} />
            <h3 style={{ fontSize: '1.1rem' }}>Tap here or Drag & Drop PDF, Word, or PPT to Audit & Embed</h3>
            <p style={{ color: '#94a3b8', marginTop: '0.5rem', fontSize: '0.85rem' }}>Max file size: 50 MB • Formats: PDF, DOCX, PPTX</p>
          </div>
        )}
      </div>

      {/* Prominent Red Alert Component for Failed PDF Audits */}
      {error && (
        <div style={{ 
          marginTop: '1.25rem', 
          background: 'rgba(239, 68, 68, 0.15)', 
          border: '1.5px solid #ef4444', 
          padding: '1rem 1.25rem', 
          borderRadius: '10px', 
          display: 'flex', 
          alignItems: 'flex-start', 
          gap: '0.75rem' 
        }}>
          <AlertOctagon size={24} style={{ color: '#ef4444', flexShrink: 0, marginTop: '2px' }} />
          <div style={{ width: '100%' }}>
            <strong style={{ color: '#fca5a5', display: 'block', fontSize: '1rem', marginBottom: '0.25rem' }}>
              ⚠️ THIS DOCUMENT CANNOT BE EMBEDDED
            </strong>
            <span style={{ color: '#f8fafc', fontSize: '0.92rem', lineHeight: '1.5' }}>
              {error}
            </span>
            {error.toLowerCase().includes('network error') && (
              <div style={{ marginTop: '0.75rem', fontSize: '0.88rem', background: 'rgba(99, 102, 241, 0.15)', padding: '0.6rem 0.8rem', borderRadius: '6px', border: '1px solid #6366f1' }}>
                <span style={{ color: '#c7d2fe' }}>💡 <strong>Localtunnel Authorization Required:</strong> If using localtunnel, click below once to authorize your browser, then try uploading again:</span>
                <div style={{ marginTop: '0.4rem' }}>
                  <a 
                    href="https://eighty-feet-unite.loca.lt" 
                    target="_blank" 
                    rel="noreferrer" 
                    style={{ color: '#a5b4fc', textDecoration: 'underline', fontWeight: '600', display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}
                  >
                    Open Authorization Link (Verification IP: 45.250.227.158) <ExternalLink size={14} />
                  </a>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {fileInfo && (
        <div style={{ marginTop: '1rem', background: '#0f172a', padding: '1rem', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <FileText size={24} style={{ color: '#34d399' }} />
            <div>
              <strong style={{ color: '#f8fafc', fontSize: '0.95rem' }}>{fileInfo.filename}</strong>
              <div style={{ fontSize: '0.85rem', color: '#94a3b8' }}>
                {fileInfo.format === 'docx' || fileInfo.filename?.toLowerCase().endsWith('.docx') || fileInfo.filename?.toLowerCase().endsWith('.doc') ? (
                  `${fileInfo.details || 'Word Document'} • ${fileInfo.total_chunks} Vector Chunks (Audit Passed)`
                ) : fileInfo.format === 'pptx' || fileInfo.filename?.toLowerCase().endsWith('.pptx') || fileInfo.filename?.toLowerCase().endsWith('.ppt') ? (
                  `${fileInfo.details || `${fileInfo.unit_count || 1} Slides`} • ${fileInfo.total_chunks} Vector Chunks (Audit Passed)`
                ) : fileInfo.format === 'xlsx' || fileInfo.filename?.toLowerCase().endsWith('.xlsx') || fileInfo.filename?.toLowerCase().endsWith('.csv') ? (
                  `${fileInfo.details || `${fileInfo.unit_count || 1} Sheets`} • ${fileInfo.total_chunks} Vector Chunks (Audit Passed)`
                ) : (
                  `${fileInfo.total_pages || fileInfo.unit_count || 1} Pages • ${fileInfo.total_chunks} Vector Chunks (Audit Passed)`
                )}
              </div>
            </div>
          </div>
          <span style={{ color: '#34d399', display: 'flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.85rem' }}>
            <CheckCircle size={18} /> Indexed
          </span>
        </div>
      )}
    </div>
  );
}
