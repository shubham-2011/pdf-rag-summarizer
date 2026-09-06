import React, { useState, useRef } from 'react';
import { uploadPdfApi } from '../api/client';
import { FileUp, Loader2, AlertOctagon, CheckCircle2, ShieldCheck, FileText, ExternalLink } from 'lucide-react';

export default function PdfUploader({ apiKey, onPdfUploaded }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef(null);

  const processFile = async (file) => {
    if (!file) return;

    const allowedExtensions = ['.pdf', '.docx', '.doc', '.pptx', '.ppt'];
    const hasValidExt = allowedExtensions.some(ext => file.name.toLowerCase().endsWith(ext));
    if (!hasValidExt) {
      setError('Unsupported File Format: Only PDF, Word (.docx, .doc), and PowerPoint (.pptx, .ppt) documents can be audited.');
      return;
    }

    // Pre-audit: 50MB limit
    const maxSizeBytes = 50 * 1024 * 1024;
    if (file.size > maxSizeBytes) {
      const fileSizeMb = (file.size / (1024 * 1024)).toFixed(2);
      setError(`File Size Exceeded: Document is ${fileSizeMb} MB. Maximum allowed threshold is 50 MB.`);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const data = await uploadPdfApi(file, apiKey);
      if (onPdfUploaded) {
        onPdfUploaded(data);
      }
    } catch (err) {
      console.error("Ingestion audit error:", err);
      setError(err.response?.data?.detail || err.message || 'Ingestion Audit Failed: Could not extract containers or create vector index.');
    } finally {
      setLoading(false);
    }
  };

  const handleFileChange = (e) => {
    const file = e.target.files && e.target.files[0];
    processFile(file);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files && e.dataTransfer.files[0];
    processFile(file);
  };

  const handleBoxClick = () => {
    if (fileInputRef.current && !loading) {
      fileInputRef.current.click();
    }
  };

  return (
    <div style={{ width: '100%' }}>
      <div 
        className={`ingestion-vault ${isDragging ? 'dragging' : ''}`}
        onClick={handleBoxClick}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        role="button"
        tabIndex={0}
      >
        <input 
          ref={fileInputRef}
          type="file" 
          accept=".pdf,.docx,.doc,.pptx,.ppt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.presentationml.presentation" 
          onChange={handleFileChange} 
          id="document-upload-input" 
          style={{ display: 'none' }} 
        />

        {loading ? (
          <div>
            <div className="vault-icon-wrap">
              <Loader2 className="animate-spin" size={24} />
            </div>
            <h3 className="vault-headline">Auditing & Indexing Document Passages...</h3>
            <p className="vault-subline">
              Extracting structural AST containers, validating text layer, and generating offline vector embeddings.
            </p>
          </div>
        ) : (
          <div>
            <div className="vault-icon-wrap">
              <FileUp size={24} strokeWidth={1.8} />
            </div>
            <h3 className="vault-headline">Select or Drop Document to Initialize Dossier</h3>
            <p className="vault-subline">
              Click to browse your filesystem or drag a file directly into this secure ingestion vault.
            </p>
            <div className="vault-security-note">
              <ShieldCheck size={14} style={{ color: 'var(--accent-cyan)' }} />
              <span>Offline Retrieval • Nomic 768d Embeddings • Max 50 MB</span>
            </div>
          </div>
        )}
      </div>

      {error && (
        <div className="audit-error-card">
          <AlertOctagon size={20} style={{ color: 'var(--accent-rose)', flexShrink: 0, marginTop: 2 }} />
          <div>
            <div className="audit-error-title">INGESTION AUDIT REJECTED</div>
            <div className="audit-error-desc">{error}</div>
            {error.toLowerCase().includes('network error') && (
              <div style={{ marginTop: '0.65rem', fontSize: '0.8rem', background: 'rgba(2, 132, 199, 0.12)', padding: '0.5rem 0.75rem', borderRadius: '4px', border: '1px solid var(--border-medium)' }}>
                <span style={{ color: '#bae6fd' }}>Notice: If using a tunnel proxy, ensure the endpoint authorization page has been bypassed in your browser.</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
