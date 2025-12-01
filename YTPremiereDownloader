import React, { useState, useRef, useEffect } from 'react';
import { Download, Play, CheckCircle, XCircle, Clock, Settings, FolderOpen } from 'lucide-react';

const YTPremiereDownloader = () => {
  const [urls, setUrls] = useState([]);
  const [urlInput, setUrlInput] = useState('');
  const [resolution, setResolution] = useState('1080p');
  const [formatMode, setFormatMode] = useState('h264_cfr');
  const [outputDir, setOutputDir] = useState('~/Downloads');
  const [currentProgress, setCurrentProgress] = useState(0);
  const [totalProgress, setTotalProgress] = useState(0);
  const [isProcessing, setIsProcessing] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const inputRef = useRef(null);

  const formatModes = {
    passthrough: { label: 'Pass-through (MP4/MKV)', desc: 'Fast download, no re-encoding' },
    prores: { label: 'Editor Ready (ProRes 422)', desc: 'Best for heavy editing' },
    h264_cfr: { label: 'Editor Ready (H.264 CFR)', desc: 'Fixes Premiere audio sync' }
  };

  const addUrl = (url) => {
    if (!url.trim()) return;
    const newVideo = {
      id: Date.now(),
      url: url.trim(),
      title: 'Fetching info...',
      status: 'pending',
      thumbnail: null,
      progress: 0
    };
    setUrls(prev => [...prev, newVideo]);
    setUrlInput('');
    
    // Simulate fetching video info
    setTimeout(() => {
      setUrls(prev => prev.map(v => 
        v.id === newVideo.id 
          ? { ...v, title: `Video ${v.id}`, thumbnail: '📹' }
          : v
      ));
    }, 1000);
  };

  const pasteFromClipboard = async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text.includes('youtube.com') || text.includes('youtu.be')) {
        addUrl(text);
      } else {
        setUrlInput(text);
      }
    } catch (err) {
      console.error('Failed to read clipboard:', err);
    }
  };

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    const text = e.dataTransfer.getData('text');
    if (text) addUrl(text);
  };

  const startDownload = () => {
    setIsProcessing(true);
    const pendingUrls = urls.filter(v => v.status === 'pending');
    
    // Simulate download process
    let completed = 0;
    pendingUrls.forEach((video, index) => {
      setTimeout(() => {
        // Update to downloading
        setUrls(prev => prev.map(v => 
          v.id === video.id ? { ...v, status: 'downloading' } : v
        ));
        
        // Simulate progress
        let progress = 0;
        const progressInterval = setInterval(() => {
          progress += Math.random() * 15;
          if (progress >= 100) {
            progress = 100;
            clearInterval(progressInterval);
            
            // Move to encoding
            setUrls(prev => prev.map(v => 
              v.id === video.id ? { ...v, status: 'encoding', progress: 100 } : v
            ));
            
            // Complete encoding
            setTimeout(() => {
              setUrls(prev => prev.map(v => 
                v.id === video.id ? { ...v, status: 'finished' } : v
              ));
              completed++;
              setTotalProgress((completed / pendingUrls.length) * 100);
              
              if (completed === pendingUrls.length) {
                setIsProcessing(false);
                setCurrentProgress(0);
              }
            }, 2000);
          } else {
            setUrls(prev => prev.map(v => 
              v.id === video.id ? { ...v, progress } : v
            ));
            setCurrentProgress(progress);
          }
        }, 300);
      }, index * 500);
    });
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'pending': return <Clock className="w-4 h-4 text-gray-400" />;
      case 'downloading': return <Download className="w-4 h-4 text-blue-500 animate-pulse" />;
      case 'encoding': return <Play className="w-4 h-4 text-purple-500 animate-pulse" />;
      case 'finished': return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'failed': return <XCircle className="w-4 h-4 text-red-500" />;
      default: return null;
    }
  };

  const clearFinished = () => {
    setUrls(prev => prev.filter(v => v.status !== 'finished'));
    setTotalProgress(0);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 text-white p-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-8 text-center">
          <h1 className="text-4xl font-bold mb-2 bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent">
            YouTube to Premiere Pro
          </h1>
          <p className="text-gray-400">Professional video downloader optimized for Adobe Premiere Pro</p>
        </div>

        {/* Main Container */}
        <div className="bg-gray-800/50 backdrop-blur-sm rounded-2xl shadow-2xl border border-gray-700 overflow-hidden">
          
          {/* Input Section */}
          <div 
            className={`p-6 border-b border-gray-700 transition-all ${dragActive ? 'bg-blue-500/10 border-blue-500' : ''}`}
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
          >
            <div className="flex gap-3 mb-4">
              <input
                ref={inputRef}
                type="text"
                value={urlInput}
                onChange={(e) => setUrlInput(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && addUrl(urlInput)}
                placeholder="Paste YouTube URL here or drag & drop..."
                className="flex-1 bg-gray-900 border border-gray-600 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <button
                onClick={pasteFromClipboard}
                className="px-6 py-3 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors font-medium"
              >
                Paste
              </button>
              <button
                onClick={() => addUrl(urlInput)}
                className="px-6 py-3 bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors font-medium flex items-center gap-2"
              >
                <Download className="w-4 h-4" />
                Add
              </button>
            </div>

            {/* Settings Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* Resolution */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Resolution</label>
                <select
                  value={resolution}
                  onChange={(e) => setResolution(e.target.value)}
                  className="w-full bg-gray-900 border border-gray-600 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="4k">4K (2160p)</option>
                  <option value="1080p">1080p (Full HD)</option>
                  <option value="720p">720p (HD)</option>
                </select>
              </div>

              {/* Format Mode */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Format Mode</label>
                <select
                  value={formatMode}
                  onChange={(e) => setFormatMode(e.target.value)}
                  className="w-full bg-gray-900 border border-gray-600 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {Object.entries(formatModes).map(([key, val]) => (
                    <option key={key} value={key}>{val.label}</option>
                  ))}
                </select>
              </div>

              {/* Output Directory */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Output Directory</label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={outputDir}
                    onChange={(e) => setOutputDir(e.target.value)}
                    className="flex-1 bg-gray-900 border border-gray-600 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                  <button className="px-3 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors">
                    <FolderOpen className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>

            <p className="mt-3 text-sm text-gray-400">{formatModes[formatMode].desc}</p>
          </div>

          {/* Queue List */}
          <div className="p-6 max-h-96 overflow-y-auto">
            {urls.length === 0 ? (
              <div className="text-center py-12 text-gray-500">
                <Download className="w-16 h-16 mx-auto mb-4 opacity-30" />
                <p>No videos in queue. Add URLs to get started.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {urls.map((video) => (
                  <div key={video.id} className="bg-gray-900/50 rounded-lg p-4 border border-gray-700">
                    <div className="flex items-center gap-4">
                      <div className="text-2xl">{video.thumbnail || '📹'}</div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          {getStatusIcon(video.status)}
                          <p className="font-medium truncate">{video.title}</p>
                        </div>
                        <p className="text-xs text-gray-500 truncate">{video.url}</p>
                        {(video.status === 'downloading' || video.status === 'encoding') && (
                          <div className="mt-2">
                            <div className="w-full bg-gray-700 rounded-full h-2 overflow-hidden">
                              <div 
                                className="bg-gradient-to-r from-blue-500 to-purple-500 h-full transition-all duration-300"
                                style={{ width: `${video.progress}%` }}
                              />
                            </div>
                            <p className="text-xs text-gray-400 mt-1">
                              {video.status === 'downloading' ? 'Downloading' : 'Encoding'} - {Math.round(video.progress)}%
                            </p>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Progress Bars */}
          {isProcessing && (
            <div className="p-6 border-t border-gray-700 space-y-4">
              <div>
                <div className="flex justify-between text-sm mb-2">
                  <span className="text-gray-400">Current File</span>
                  <span className="text-blue-400">{Math.round(currentProgress)}%</span>
                </div>
                <div className="w-full bg-gray-700 rounded-full h-3 overflow-hidden">
                  <div 
                    className="bg-gradient-to-r from-blue-500 to-blue-600 h-full transition-all duration-300"
                    style={{ width: `${currentProgress}%` }}
                  />
                </div>
              </div>
              <div>
                <div className="flex justify-between text-sm mb-2">
                  <span className="text-gray-400">Total Progress</span>
                  <span className="text-purple-400">{Math.round(totalProgress)}%</span>
                </div>
                <div className="w-full bg-gray-700 rounded-full h-3 overflow-hidden">
                  <div 
                    className="bg-gradient-to-r from-purple-500 to-purple-600 h-full transition-all duration-300"
                    style={{ width: `${totalProgress}%` }}
                  />
                </div>
              </div>
            </div>
          )}

          {/* Action Buttons */}
          <div className="p-6 border-t border-gray-700 flex gap-3">
            <button
              onClick={startDownload}
              disabled={isProcessing || urls.filter(v => v.status === 'pending').length === 0}
              className="flex-1 px-6 py-3 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 disabled:from-gray-600 disabled:to-gray-600 disabled:cursor-not-allowed rounded-lg transition-all font-medium flex items-center justify-center gap-2"
            >
              <Download className="w-5 h-5" />
              {isProcessing ? 'Processing...' : `Start Download (${urls.filter(v => v.status === 'pending').length})`}
            </button>
            <button
              onClick={clearFinished}
              className="px-6 py-3 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors font-medium"
            >
              Clear Finished
            </button>
          </div>
        </div>

        {/* Info Footer */}
        <div className="mt-6 text-center text-sm text-gray-500">
          <p>FFmpeg-powered • Hardware acceleration enabled • VFR to CFR conversion</p>
        </div>
      </div>
    </div>
  );
};

export default YTPremiereDownloader;