import React, { useState, useRef, useEffect } from 'react';
import { X, UploadCloud, Image as ImageIcon, MapPin, CheckCircle, AlertCircle } from 'lucide-react';
import { api } from '../../api/client';

export default function UploadModal({ isOpen, onClose }) {
    const [files, setFiles] = useState([]);
    const [previews, setPreviews] = useState([]);
    const [isDragging, setIsDragging] = useState(false);
    const [status, setStatus] = useState('idle'); // 'idle' | 'uploading' | 'success' | 'error'
    const [errorMsg, setErrorMsg] = useState('');
    const fileInputRef = useRef(null);
    const closeTimerRef = useRef(null);
    const uploadCounterRef = useRef(0);

    const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB

    // setTimeout cleanup on unmount
    useEffect(() => {
        return () => {
            if (closeTimerRef.current) clearTimeout(closeTimerRef.current);
        };
    }, []);

    if (!isOpen) return null;

    const supportedTypes = ['image/jpeg', 'image/png', 'image/heic'];

    const handleFiles = (selectedFiles) => {
        if (!selectedFiles || selectedFiles.length === 0) return;

        const validFiles = Array.from(selectedFiles).filter(f => {
            const typeOk = supportedTypes.includes(f.type) || f.name.toLowerCase().endsWith('.heic');
            const sizeOk = f.size <= MAX_FILE_SIZE;
            if (!sizeOk) {
                setErrorMsg(`${f.name}: 50MB를 초과합니다.`);
                setStatus('error');
            }
            return typeOk && sizeOk;
        });

        if (validFiles.length !== selectedFiles.length) {
            setErrorMsg('일부 파일 형식이 제외되었습니다. (JPG, PNG, HEIC만 가능)');
            setStatus('error');
            setTimeout(() => { if (status !== 'uploading') setStatus('idle'); }, 3000);
        }

        if (validFiles.length === 0) return;

        setFiles(prev => [...prev, ...validFiles]);
        if (status === 'error') setStatus('idle');
        setErrorMsg('');

        // Create previews
        validFiles.forEach(file => {
            const reader = new FileReader();
            reader.onloadend = () => {
                setPreviews(prev => [...prev, reader.result]);
            };
            reader.readAsDataURL(file);
        });
    };

    const removeFile = (index) => {
        setFiles(prev => prev.filter((_, i) => i !== index));
        setPreviews(prev => prev.filter((_, i) => i !== index));
    };

    const handleDragOver = (e) => {
        e.preventDefault();
        setIsDragging(true);
    };

    const handleDragLeave = (e) => {
        e.preventDefault();
        setIsDragging(false);
    };

    const handleDrop = (e) => {
        e.preventDefault();
        setIsDragging(false);
        handleFiles(e.dataTransfer.files);
    };

    const handleUpload = async () => {
        if (files.length === 0) return;

        setStatus('uploading');
        try {
            await Promise.all(files.map(file => api.uploadPhoto(file)));
            setStatus('success');
            uploadCounterRef.current += 1;
            window.dispatchEvent(new CustomEvent('photoUploaded', { detail: { seq: uploadCounterRef.current } }));
            // 2초 후 자동 닫기 (ref로 cleanup 가능하게)
            closeTimerRef.current = setTimeout(() => {
                handleClose();
            }, 2000);
        } catch (error) {
            console.error("Upload error:", error);
            setStatus('error');
            setErrorMsg(error.response?.data?.detail || "업로드 중 오류가 발생했습니다.");
        }
    };

    const handleClose = () => {
        setFiles([]);
        setPreviews([]);
        setStatus('idle');
        setErrorMsg('');
        setIsDragging(false);
        onClose();
    };

    return (
        <div className="fixed inset-0 z-50 flex items-end md:items-end justify-center md:justify-start">
            <div
                className="absolute inset-0 bg-black/40 md:bg-transparent backdrop-blur-sm md:backdrop-blur-none transition-opacity"
                onClick={handleClose}
            ></div>

            <div
                className="bg-[#FDFBF7] w-full md:w-[380px] h-[90vh] md:h-auto md:max-h-[85vh] rounded-t-3xl md:rounded-3xl overflow-hidden shadow-[0_8px_30px_rgb(0,0,0,0.12)] border border-transparent md:border-[#EAE5D9] relative flex flex-col z-10 
                           md:mb-6 md:ml-[104px]
                           animate-in slide-in-from-bottom-10 md:slide-in-from-bottom-5 md:slide-in-from-left-2 md:zoom-in-95 origin-bottom-left duration-300"
                onClick={(e) => e.stopPropagation()}
            >
                {/* Header */}
                <div className="px-5 py-4 border-b border-[#EAE5D9] flex justify-between items-center bg-white sticky top-0 z-10 shrink-0 rounded-t-3xl md:rounded-t-3xl">
                    <h2 className="text-lg font-bold text-[#6B6653] flex items-center gap-2">
                        <UploadCloud className="text-[#B6694E]" size={22} />
                        Upload Photos
                    </h2>
                    <button
                        onClick={handleClose}
                        className="p-1.5 text-[#6B6653] hover:bg-[#F2EEE4] rounded-full transition-colors"
                        disabled={status === 'uploading'}
                    >
                        <X size={18} />
                    </button>
                </div>

                {/* Body (Scrollable) */}
                <div className="p-5 flex-1 overflow-y-auto w-full max-w-full">

                    {/* File Dropzone - Shows even when files exist to allow appending more */}
                    <div
                        className={`w-full ${files.length > 0 ? 'h-24 mb-4' : 'aspect-square md:aspect-auto md:h-48'} border-2 border-dashed rounded-2xl flex flex-col items-center justify-center p-5 text-center transition-colors cursor-pointer ${isDragging
                            ? 'border-[#B6694E] bg-[#EAE5D9]/30'
                            : 'border-[#EAE5D9] bg-white hover:bg-[#F2EEE4]/30'
                            }`}
                        onDragOver={handleDragOver}
                        onDragLeave={handleDragLeave}
                        onDrop={handleDrop}
                        onClick={() => fileInputRef.current?.click()}
                    >
                        <input
                            type="file"
                            multiple
                            ref={fileInputRef}
                            className="hidden"
                            accept=".jpg,.jpeg,.png,.heic"
                            onChange={(e) => handleFiles(e.target.files)}
                        />
                        {files.length === 0 ? (
                            <>
                                <div className="w-12 h-12 bg-[#F2EEE4] text-[#D7AD7E] rounded-full flex items-center justify-center mb-3">
                                    <ImageIcon size={24} />
                                </div>
                                <h3 className="text-base font-semibold text-[#6B6653] mb-1">
                                    Click or drag files here
                                </h3>
                                <p className="text-xs text-gray-500 mb-4">
                                    Maximum file size 50 MB
                                </p>
                                <div className="flex gap-2">
                                    <span className="text-[10px] font-bold tracking-wider px-2 py-1 bg-gray-100 text-gray-600 rounded">JPG</span>
                                    <span className="text-[10px] font-bold tracking-wider px-2 py-1 bg-gray-100 text-gray-600 rounded">PNG</span>
                                    <span className="text-[10px] font-bold tracking-wider px-2 py-1 bg-gray-100 text-gray-600 rounded">HEIC</span>
                                </div>
                            </>
                        ) : (
                            <div className="flex flex-col items-center">
                                <UploadCloud size={24} className="text-[#D7AD7E] mb-2" />
                                <span className="text-sm font-semibold text-[#6B6653]">Add more photos</span>
                            </div>
                        )}
                    </div>

                    {/* File Previews */}
                    {files.length > 0 && (
                        <div className="w-full bg-white border border-[#EAE5D9] rounded-2xl overflow-hidden shadow-sm relative mb-4">
                            {/* Horizontal scrollable previews */}
                            <div className="flex overflow-x-auto snap-x h-48 md:h-56 bg-gray-50 border-b border-[#EAE5D9] scrollbar-hide">
                                {previews.map((preview, idx) => (
                                    <div key={idx} className="min-w-full h-full relative snap-center shrink-0">
                                        <img src={preview} alt={`Preview ${idx}`} className="w-full h-full object-cover" />
                                        {status !== 'uploading' && status !== 'success' && (
                                            <button
                                                onClick={() => removeFile(idx)}
                                                className="absolute top-3 right-3 text-red-500 hover:text-red-700 bg-white/90 backdrop-blur-sm rounded-full p-1.5 shadow-sm"
                                            >
                                                <X size={16} />
                                            </button>
                                        )}
                                        <div className="absolute bottom-3 right-3 bg-black/60 backdrop-blur-md text-white px-2 py-1 rounded text-xs font-medium tracking-wider shadow-sm">
                                            {idx + 1} / {files.length}
                                        </div>
                                    </div>
                                ))}
                            </div>

                            <div className="p-3 flex items-center justify-between bg-white/90 backdrop-blur-sm absolute bottom-0 left-0 right-0 border-t border-[#EAE5D9]/50">
                                <div className="flex flex-col truncate pr-4">
                                    <span className="font-medium text-sm text-[#6B6653] truncate">
                                        {files.length === 1 ? files[0].name : `${files[0].name} 외 ${files.length - 1}개 파일`}
                                    </span>
                                    <span className="text-[10px] text-gray-500">
                                        {(files.reduce((acc, f) => acc + f.size, 0) / (1024 * 1024)).toFixed(2)} MB 총합
                                    </span>
                                </div>
                                {status !== 'uploading' && status !== 'success' && (
                                    <button
                                        onClick={() => { setFiles([]); setPreviews([]); setStatus('idle'); }}
                                        className="text-red-500 hover:text-red-600 hover:bg-red-50 px-2 py-1 rounded transition-colors text-xs font-semibold shrink-0"
                                    >
                                        비우기
                                    </button>
                                )}
                            </div>
                        </div>
                    )}

                    {/* GPS Warning */}
                    <div className="mt-5 flex items-start gap-2.5 p-3.5 bg-[#EAE5D9]/30 rounded-xl border border-[#D7AD7E]/20">
                        <MapPin className="text-[#B6694E] shrink-0 mt-0.5" size={16} />
                        <p className="text-[11px] md:text-xs text-[#6B6653]/90 leading-relaxed">
                            <strong className="block text-[#6B6653] mb-0.5 text-xs">Location Data Recommended</strong>
                            위치 정보(GPS)가 포함된 사진은 장소 기반 자동 정리에 최적화됩니다.
                        </p>
                    </div>

                    {/* Status Messages */}
                    {status === 'error' && (
                        <div className="mt-4 flex items-center gap-2 text-red-600 text-xs bg-red-50 p-2.5 rounded-lg border border-red-100">
                            <AlertCircle size={14} />
                            {errorMsg}
                        </div>
                    )}

                    {status === 'success' && (
                        <div className="mt-4 flex items-center gap-2 text-green-600 text-xs bg-green-50 p-2.5 rounded-lg border border-green-100">
                            <CheckCircle size={14} />
                            {files.length}개의 사진 업로드가 완료되었습니다!
                        </div>
                    )}
                </div>

                {/* Footer / Upload Button */}
                <div className="p-5 border-t border-[#EAE5D9] bg-[#FDFBF7] shrink-0 rounded-b-3xl md:rounded-b-3xl">
                    <button
                        onClick={handleUpload}
                        disabled={files.length === 0 || status === 'uploading' || status === 'success'}
                        className={`w-full py-3 rounded-xl font-bold flex items-center justify-center transition-all shadow-sm ${files.length === 0 || status === 'uploading' || status === 'success'
                            ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                            : 'bg-[#D7AD7E] hover:bg-[#c49b6c] text-white hover:shadow-md'
                            }`}
                    >
                        {status === 'idle' && `Upload ${files.length > 0 ? files.length + ' Photos' : 'Photo'}`}
                        {status === 'uploading' && (
                            <>
                                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin mr-2"></div>
                                Uploading {files.length} Photos...
                            </>
                        )}
                        {status === 'success' && 'Done!'}
                        {status === 'error' && 'Retry Failed'}
                    </button>
                </div>
            </div>
        </div>
    );
}
