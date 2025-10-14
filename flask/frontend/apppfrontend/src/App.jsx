// frontend/apppfrontend/src/App.jsx
import React, { useState, useEffect, useCallback, useMemo } from 'react';

const API_BASE = 'http://localhost:5000';

const App = () => {
  // ✅ ALL HOOKS AT TOP — NO CONDITIONAL HOOKS
  const [user, setUser] = useState(null);
  const [authMode, setAuthMode] = useState('login'); // 'login' or 'register'
  const [authForm, setAuthForm] = useState({ username: '', password: '' });

  const [file, setFile] = useState(null);
  const [task, setTask] = useState({
    id: null,
    status: 'idle',
    logs: [],
    progress: 0,
    currentStep: '',
    pdfFilename: null,
  });
  const [isDragOver, setIsDragOver] = useState(false);

  // --- AUTH CHECK ON LOAD ---
  useEffect(() => {
    const checkAuth = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/user`, { credentials: 'include' });
        const data = await res.json();
        if (data.user) setUser(data);
      } catch (err) {
        console.error('Auth check failed:', err);
      }
    };
    checkAuth();
  }, []);

  // --- UPLOAD WITH REAL PROGRESS ---
  const handleUpload = () => {
    if (!file) return;

    setTask({
      id: null,
      status: 'uploading',
      logs: ['Starting upload...'],
      progress: 0,
      currentStep: 'Uploading',
      pdfFilename: null,
    });

    const formData = new FormData();
    formData.append('videoFile', file);

    const xhr = new XMLHttpRequest();
    xhr.open('POST', `${API_BASE}/upload`);
    xhr.withCredentials = true;

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        const percent = Math.round((e.loaded / e.total) * 100);
        setTask(prev => ({ ...prev, progress: percent }));
      }
    };

    xhr.onload = () => {
      if (xhr.status === 200) {
        const data = JSON.parse(xhr.responseText);
        setTask(prev => ({
          ...prev,
          id: data.task_id,
          status: 'processing',
          logs: [...prev.logs, `Upload complete! Starting pipeline (Task ID: ${data.task_id})...`],
          progress: 0,
          currentStep: 'Initializing...',
        }));
      } else {
        const errorData = JSON.parse(xhr.responseText);
        setTask({
          status: 'error',
          logs: [`Upload failed: ${errorData.error || 'Unknown error'}`],
          progress: 0,
          id: null,
          currentStep: '',
          pdfFilename: null,
        });
      }
    };

    xhr.onerror = () => {
      setTask({
        status: 'error',
        logs: ['Network error during upload.'],
        progress: 0,
        id: null,
        currentStep: '',
        pdfFilename: null,
      });
    };

    xhr.send(formData);
  };

  // --- PROGRESS POLLING ---
  useEffect(() => {
    if (task.status !== 'processing' || !task.id) return;

    const intervalId = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/progress/${task.id}`, { credentials: 'include' });
        if (!res.ok) throw new Error('Failed');
        const data = await res.json();
        if (data.status === 'running' && data.message) {
          const msg = data.message;
          setTask(prev => ({ ...prev, logs: [...prev.logs, msg].slice(-100) }));
          if (msg.startsWith('PROGRESS:')) {
            setTask(prev => ({ ...prev, progress: parseInt(msg.split(':')[1]) }));
          } else if (msg.includes('Stage 1:')) {
            setTask(prev => ({ ...prev, currentStep: 'Audio Conversion', progress: 0 }));
          } else if (msg.includes('Stage 2:')) {
            setTask(prev => ({ ...prev, currentStep: 'Transcription', progress: 0 }));
          } else if (msg.includes('Stage 3:')) {
            setTask(prev => ({ ...prev, currentStep: 'Summarization', progress: 0 }));
          } else if (msg.includes('Stage 4:')) {
            setTask(prev => ({ ...prev, currentStep: 'Note Generation', progress: 0 }));
          } else if (msg.startsWith('FINAL_PDF:')) {
            setTask(prev => ({ ...prev, pdfFilename: msg.split(':')[1] }));
          } else if (msg.startsWith('PIPELINE ERROR') || msg.startsWith('❌')) {
            setTask(prev => ({ ...prev, status: 'error' }));
          } else if (msg === 'TASK_COMPLETE') {
            setTask(prev => ({ ...prev, status: 'completed', progress: 100 }));
          }
        }
      } catch (err) {
        setTask(prev => ({
          ...prev,
          status: 'error',
          logs: [...prev.logs, 'Progress fetch failed'],
        }));
      }
    }, 2000);

    return () => clearInterval(intervalId);
  }, [task.id, task.status]);

  // --- AUTH HANDLERS ---
  const handleAuthChange = (e) => {
    const { name, value } = e.target;
    setAuthForm(prev => ({ ...prev, [name]: value }));
  };

  const handleAuthSubmit = async (e) => {
    e.preventDefault();
    const url = authMode === 'login' ? `${API_BASE}/api/login` : `${API_BASE}/api/register`;
    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(authForm),
        credentials: 'include',
      });
      const data = await res.json();
      if (res.ok) {
        setUser({ id: data.user_id, username: data.username });
      } else {
        alert(data.error || 'Auth failed');
      }
    } catch (err) {
      console.error(err);
      alert('Network error');
    }
  };

  const handleLogout = async () => {
    await fetch(`${API_BASE}/api/logout`, { method: 'POST', credentials: 'include' });
    setUser(null);
    setFile(null);
    setTask({ id: null, status: 'idle', logs: [], progress: 0, currentStep: '', pdfFilename: null });
  };

  // --- FILE HANDLERS ---
  const handleFileSelect = (f) => {
    if (f && f.type.startsWith('video/')) setFile(f);
    else alert('Please select a valid video file.');
  };

  const handleFileChange = (e) => {
    if (e.target.files?.[0]) handleFileSelect(e.target.files[0]);
  };

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files?.[0]) handleFileSelect(e.dataTransfer.files[0]);
  }, []);

  const handleDragEvents = useCallback((e) => {
    e.preventDefault();
    if (e.type === 'dragenter' || e.type === 'dragover') setIsDragOver(true);
    else if (e.type === 'dragleave') setIsDragOver(false);
  }, []);

  const handleReset = () => {
    setFile(null);
    setTask({ id: null, status: 'idle', logs: [], progress: 0, currentStep: '', pdfFilename: null });
  };

  // --- RENDER AUTH SCREEN ---
  if (!user) {
    return (
      <div className="bg-gray-900 text-white min-h-screen flex items-center justify-center p-4">
        <div className="w-full max-w-md bg-gray-800 rounded-xl shadow-2xl p-8">
          <h2 className="text-3xl font-bold text-center mb-6 text-purple-400">
            {authMode === 'login' ? 'Welcome Back' : 'Create Account'}
          </h2>
          <form onSubmit={handleAuthSubmit} className="space-y-4">
            <input
              name="username"
              placeholder="Username"
              className="w-full p-3 rounded bg-gray-700 border border-gray-600 focus:outline-none focus:ring-2 focus:ring-purple-500"
              value={authForm.username}
              onChange={handleAuthChange}
              required
            />
            <input
              name="password"
              type="password"
              placeholder="Password"
              className="w-full p-3 rounded bg-gray-700 border border-gray-600 focus:outline-none focus:ring-2 focus:ring-purple-500"
              value={authForm.password}
              onChange={handleAuthChange}
              required
            />
            <button
              type="submit"
              className="w-full py-3 bg-purple-600 rounded-lg font-semibold hover:bg-purple-700 transition"
            >
              {authMode === 'login' ? 'Log In' : 'Register'}
            </button>
          </form>
          <p className="text-center mt-4">
            {authMode === 'login' ? "Don't have an account? " : "Already have an account? "}
            <button
              onClick={() => setAuthMode(authMode === 'login' ? 'register' : 'login')}
              className="text-purple-400 hover:underline"
            >
              {authMode === 'login' ? 'Sign Up' : 'Log In'}
            </button>
          </p>
        </div>
      </div>
    );
  }

  // --- MAIN APP UI ---
  const renderContent = () => {
    switch (task.status) {
      case 'uploading':
        return (
          <div className="flex flex-col items-center justify-center space-y-4">
            <Spinner />
            <h2 className="text-lg font-semibold">Uploading Video...</h2>
            <div className="w-full bg-gray-700 rounded-full h-2.5">
              <div
                className="bg-purple-600 h-2.5 rounded-full transition-all duration-300"
                style={{ width: `${task.progress}%` }}
              ></div>
            </div>
            <p className="text-gray-400">{task.progress}%</p>
          </div>
        );
      case 'processing':
      case 'completed':
      case 'error':
        return <ProgressView task={task} onReset={handleReset} apiBase={API_BASE} />;
      default:
        return (
          <UploadView
            file={file}
            isDragOver={isDragOver}
            onFileChange={handleFileChange}
            onDrop={handleDrop}
            onDragEvents={handleDragEvents}
            onUpload={handleUpload}
            onClearFile={() => setFile(null)}
          />
        );
    }
  };

  return (
    <div className="bg-gray-900 text-white min-h-screen flex flex-col">
      <header className="p-4 bg-gray-800 flex justify-between items-center">
        <h1 className="text-2xl font-bold text-purple-400">Video to Notes AI</h1>
        <div className="flex items-center space-x-4">
          <span className="text-gray-300">Hello, {user.username}</span>
          <button
            onClick={handleLogout}
            className="px-4 py-2 bg-gray-700 rounded hover:bg-gray-600 transition"
          >
            Logout
          </button>
        </div>
      </header>

      <main className="flex-1 flex items-center justify-center p-4">
        <div className="w-full max-w-2xl bg-gray-800 rounded-xl shadow-2xl p-6 sm:p-8">
          {renderContent()}
        </div>
      </main>

      <footer className="p-4 text-center text-gray-500 text-sm">
        Powered by Flask, React & Open-Source AI
      </footer>
    </div>
  );
};

// --- SUBCOMPONENTS (same as before) ---
const UploadView = ({ file, isDragOver, onFileChange, onDrop, onDragEvents, onUpload, onClearFile }) => (
  <div className="space-y-6">
    <label
      htmlFor="video-upload"
      onDrop={onDrop}
      onDragOver={onDragEvents}
      onDragEnter={onDragEvents}
      onDragLeave={onDragEvents}
      className={`block h-48 border-2 border-dashed rounded-lg flex flex-col items-center justify-center cursor-pointer transition ${
        isDragOver ? 'border-purple-500 bg-gray-700' : 'border-gray-600 hover:border-purple-400'
      }`}
    >
      <input id="video-upload" type="file" className="hidden" accept="video/*" onChange={onFileChange} />
      <FileIcon />
      <p className="mt-2 text-gray-400">
        {isDragOver ? 'Drop your video!' : 'Drag & drop a video, or click to select'}
      </p>
    </label>

    {file && (
      <div className="flex justify-between items-center bg-gray-700 p-3 rounded">
        <span className="truncate">{file.name}</span>
        <button onClick={onClearFile} className="text-gray-400 hover:text-white">
          <CloseIcon />
        </button>
      </div>
    )}

    <button
      onClick={onUpload}
      disabled={!file}
      className="w-full py-3 bg-purple-600 rounded-lg font-semibold disabled:opacity-50 disabled:cursor-not-allowed hover:bg-purple-700 transition"
    >
      Generate Notes
    </button>
  </div>
);

const ProgressView = ({ task, onReset, apiBase }) => {
  const steps = useMemo(() => [
    { name: 'Audio Conversion', icon: <AudioIcon /> },
    { name: 'Transcription', icon: <TextIcon /> },
    { name: 'Summarization', icon: <SummaryIcon /> },
    { name: 'Note Generation', icon: <NoteIcon /> },
  ], []);

  const currentStepIndex = steps.findIndex(s => s.name === task.currentStep);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-gray-300 mb-4">
          {task.status === 'completed' ? '✅ Done!' :
           task.status === 'error' ? '❌ Failed' :
           `Processing: ${task.currentStep || 'Starting...'}`}
        </h2>

        <div className="flex items-center space-x-2">
          {steps.map((step, i) => (
            <React.Fragment key={step.name}>
              <div className="flex flex-col items-center">
                <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
                  i < currentStepIndex || task.status === 'completed' ? 'bg-green-500' :
                  i === currentStepIndex ? 'bg-purple-600 animate-pulse' : 'bg-gray-600'
                }`}>
                  {i < currentStepIndex || task.status === 'completed' ? <CheckIcon /> : step.icon}
                </div>
                <span className="text-xs mt-1 text-gray-400">{step.name}</span>
              </div>
              {i < steps.length - 1 && (
                <div className={`flex-1 h-1 rounded ${
                  i < currentStepIndex || task.status === 'completed' ? 'bg-green-500' : 'bg-gray-600'
                }`} />
              )}
            </React.Fragment>
          ))}
        </div>

        {task.status === 'processing' && (
          <div className="mt-4">
            <div className="w-full bg-gray-700 h-2.5 rounded-full">
              <div
                className="bg-purple-600 h-2.5 rounded-full transition-all duration-300"
                style={{ width: `${task.progress}%` }}
              />
            </div>
          </div>
        )}
      </div>

      <div className="bg-gray-900 p-3 h-32 overflow-y-auto font-mono text-sm text-gray-400 border border-gray-700 rounded">
        {task.logs.map((log, i) => (
          <div key={i}> {log}</div>
        ))}
      </div>

      <div className="flex flex-col sm:flex-row gap-3 pt-4">
        {task.status === 'completed' && task.pdfFilename && (
          <a
            href={`${apiBase}/download/${task.id}/${task.pdfFilename}`}
            download
            className="flex-1 py-2 bg-green-600 text-center rounded hover:bg-green-700 transition"
          >
            Download PDF
          </a>
        )}
        <button
          onClick={onReset}
          className="flex-1 py-2 bg-gray-700 rounded hover:bg-gray-600 transition"
        >
          {task.status === 'error' ? 'Try Again' : 'New Video'}
        </button>
      </div>
    </div>
  );
};

// --- ICONS (same as before) ---
const FileIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" className="w-10 h-10 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
  </svg>
);

const CloseIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
  </svg>
);

const Spinner = () => (
  <svg className="animate-spin h-5 w-5 text-purple-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
  </svg>
);

const CheckCircleIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
);

const ErrorIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
);

const CheckIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
  </svg>
);

const AudioIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.858 5.858a3 3 0 114.243 4.243L4.243 15.96a3 3 0 01-4.243-4.243l5.858-5.858z" />
  </svg>
);

const TextIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h7" />
  </svg>
);

const SummaryIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
  </svg>
);

const NoteIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
  </svg>
);

export default App;