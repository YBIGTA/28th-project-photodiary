import React, { useState, useRef } from 'react';
import { X, UploadCloud, Image as ImageIcon, MapPin, CheckCircle, AlertCircle } from 'lucide-react';
import { api } from '../../api/client';

export default function UploadModal({ isOpen, onClose }) {
    const [file, setFile] = useState(null);
    const [preview, setPreview] = useState(null);
    const [isDragging, setIsDragging] = useState(false);
    const [status, setStatus] = useState('idle'); // 'idle' | 'uploading' | 'success' | 'error'
    const [errorMsg, setErrorMsg] = useState('');
    const fileInputRef = useRef(null);

    if (!isOpen) return null;

    const supportedTypes = ['image/jpeg', 'image/png', 'image/heic'];

    const handleFile = (selectedFile) => {
        if (!selectedFile) return;

        // type check
        if (!supportedTypes.includes(selectedFile.type) && !selectedFile.name.toLowerCase().endsWith('.heic')) {
            setErrorMsg('지원하지 않는 파일 형식입니다. (JPG, PNG, HEIC만 가능)');
            setStatus('error');
            return;
        }

        setFile(selectedFile);
        setStatus('idle');
        setErrorMsg('');

        // Create preview
        const reader = new FileReader();
        reader.onloadend = () => {
            setPreview(reader.result);
        };
        reader.readAsDataURL(selectedFile);
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
        const droppedFile = e.dataTransfer.files[0];
        handleFile(droppedFile);
    };

    const handleUpload = async () => {
        if (!file) return;

        setStatus('uploading');
        try {
            await api.uploadPhoto(file);
            setStatus('success');
            // 2초 후 자동 닫기
            setTimeout(() => {
                handleClose();
            }, 2000);
        } catch (error) {
            console.error("Upload error:", error);
            setStatus('error');
            setErrorMsg(error.response?.data?.detail || "업로드 중 오류가 발생했습니다.");
        }
    };

    const handleClose = () => {
        setFile(null);
        setPreview(null);
        setStatus('idle');
        setErrorMsg('');
        setIsDragging(false);
        onClose();
    };

    // Responsive design: Full screen bottom sheet on mobile, small floating dialog on PC
    return (
        <div className="fixed inset-0 z-50 flex items-end md:items-end justify-center md:justify-start">
            {/* Backdrop: Dark on mobile, transparent on PC (allows clicking outside to close without blocking screen) */}
            <div
                className="absolute inset-0 bg-black/40 md:bg-transparent backdrop-blur-sm md:backdrop-blur-none transition-opacity"
                onClick={handleClose}
            ></div>

            {/* Modal Dialog Container */}
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
                        Upload Photo
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

                    {/* File Dropzone */}
                    {!file && (
                        <div
                            className={`w-full aspect-square md:aspect-auto md:h-48 border-2 border-dashed rounded-2xl flex flex-col items-center justify-center p-5 text-center transition-colors cursor-pointer ${isDragging
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
                                ref={fileInputRef}
                                className="hidden"
                                accept=".jpg,.jpeg,.png,.heic"
                                onChange={(e) => handleFile(e.target.files[0])}
                            />
                            <div className="w-12 h-12 bg-[#F2EEE4] text-[#D7AD7E] rounded-full flex items-center justify-center mb-3">
                                <ImageIcon size={24} />
                            </div>
                            <h3 className="text-base font-semibold text-[#6B6653] mb-1">
                                Click or drag file here
                            </h3>
                            <p className="text-xs text-gray-500 mb-4">
                                Maximum file size 50 MB
                            </p>

                            <div className="flex gap-2">
                                <span className="text-[10px] font-bold tracking-wider px-2 py-1 bg-gray-100 text-gray-600 rounded">JPG</span>
                                <span className="text-[10px] font-bold tracking-wider px-2 py-1 bg-gray-100 text-gray-600 rounded">PNG</span>
                                <span className="text-[10px] font-bold tracking-wider px-2 py-1 bg-gray-100 text-gray-600 rounded">HEIC</span>
                            </div>
                        </div>
                    )}

                    {/* File Preview */}
                    {file && (
                        <div className="w-full bg-white border border-[#EAE5D9] rounded-2xl overflow-hidden shadow-sm relative mb-4">
                            {preview ? (
                                <img src={preview} alt="Preview" className="w-full h-48 md:h-56 object-cover" />
                            ) : (
                                <div className="w-full h-48 md:h-56 flex bg-gray-100 items-center justify-center text-gray-400">
                                    <ImageIcon size={40} opacity={0.5} />
                                </div>
                            )}

                            <div className="p-3 flex items-center justify-between bg-white/90 backdrop-blur-sm absolute bottom-0 left-0 right-0 border-t border-[#EAE5D9]">
                                <div className="flex flex-col truncate pr-4">
                                    <span className="font-medium text-sm text-[#6B6653] truncate">{file.name}</span>
                                    <span className="text-[10px] text-gray-500">{(file.size / (1024 * 1024)).toFixed(2)} MB</span>
                                </div>
                                {status !== 'uploading' && status !== 'success' && (
                                    <button
                                        onClick={() => { setFile(null); setPreview(null); setStatus('idle'); }}
                                        className="text-red-400 hover:text-red-500 p-1 bg-red-50 rounded"
                                    >
                                        <X size={16} />
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
                            업로드가 완료되었습니다!
                        </div>
                    )}
                </div>

                {/* Footer / Upload Button */}
                <div className="p-5 border-t border-[#EAE5D9] bg-[#FDFBF7] shrink-0 rounded-b-3xl md:rounded-b-3xl">
                    <button
                        onClick={handleUpload}
                        disabled={!file || status === 'uploading' || status === 'success'}
                        className={`w-full py-3 rounded-xl font-bold flex items-center justify-center transition-all shadow-sm ${!file || status === 'uploading' || status === 'success'
                            ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                            : 'bg-[#D7AD7E] hover:bg-[#c49b6c] text-white hover:shadow-md'
                            }`}
                    >
                        {status === 'idle' && 'Upload Photo'}
                        {status === 'uploading' && (
                            <>
                                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin mr-2"></div>
                                Uploading...
                            </>
                        )}
                        {status === 'success' && 'Done!'}
                        {status === 'error' && 'Retry'}
                    </button>
                </div>
            </div>
        </div>
    );
}
