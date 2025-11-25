import { useRef, useEffect, useState } from 'react';

interface CameraModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCapture: (imageDataUrl: string) => void;
}

const CameraModal = ({ isOpen, onClose, onCapture }: CameraModalProps) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [capturedImage, setCapturedImage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      startCamera();
    } else {
      stopCamera();
      setCapturedImage(null);
      setError(null);
    }

    return () => {
      stopCamera();
    };
  }, [isOpen]);

  const startCamera = async () => {
    try {
      const constraints: MediaStreamConstraints = {
        video: {
          facingMode: { ideal: 'environment' },
          width: { ideal: 1280 },
          height: { ideal: 720 }
        }
      };

      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        streamRef.current = stream;
      }
    } catch (err: any) {
      console.error('無法訪問攝像頭:', err);
      
      let errorMessage = '無法訪問攝像頭。';
      
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        errorMessage = '攝像頭權限被拒絕。請在系統設置中允許應用訪問攝像頭。';
      } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
        errorMessage = '未找到攝像頭設備。請確保攝像頭已連接並正常工作。';
      } else if (err.name === 'NotReadableError' || err.name === 'TrackStartError') {
        errorMessage = '攝像頭無法讀取。可能被其他應用程序佔用。';
      } else if (err.name === 'OverconstrainedError' || err.name === 'ConstraintNotSatisfiedError') {
        try {
          const fallbackStream = await navigator.mediaDevices.getUserMedia({
            video: true
          });
          if (videoRef.current) {
            videoRef.current.srcObject = fallbackStream;
            streamRef.current = fallbackStream;
          }
          return;
        } catch (fallbackErr) {
          errorMessage = '無法訪問攝像頭。請檢查設備連接和權限設置。';
        }
      }
      
      setError(errorMessage);
    }
  };

  const stopCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
  };

  const handleCapture = () => {
    if (videoRef.current) {
      const canvas = document.createElement('canvas');
      canvas.width = videoRef.current.videoWidth;
      canvas.height = videoRef.current.videoHeight;
      
      const ctx = canvas.getContext('2d');
      if (ctx) {
        ctx.drawImage(videoRef.current, 0, 0);
        const imageDataUrl = canvas.toDataURL('image/jpeg', 0.9);
        setCapturedImage(imageDataUrl);
        stopCamera();
      }
    }
  };

  const handleUsePhoto = () => {
    if (capturedImage) {
      onCapture(capturedImage);
      onClose();
    }
  };

  const handleRetake = () => {
    setCapturedImage(null);
    startCamera();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/75 flex items-center justify-center z-[1000] backdrop-blur-sm" onClick={onClose}>
      <div className="bg-white rounded-xl w-[90%] max-w-[600px] max-h-[90vh] flex flex-col shadow-[0_8px_32px_rgba(0,0,0,0.2)] overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="flex justify-between items-center py-5 px-6 border-b border-gray-200">
          <h3 className="m-0 text-lg font-semibold text-gray-800 font-sans">拍攝照片</h3>
          <button className="bg-transparent border-none text-[28px] text-gray-600 cursor-pointer p-0 w-8 h-8 flex items-center justify-center rounded transition-colors hover:bg-gray-100 hover:text-gray-800" onClick={onClose}>×</button>
        </div>

        <div className="flex-1 flex items-center justify-center p-6 min-h-[400px] bg-gray-50">
          {error ? (
            <div className="text-center py-10 px-5">
              <p className="text-red-600 mb-5 text-sm">{error}</p>
              <button className="bg-mit-red text-white py-2.5 px-5 border-none rounded-md text-sm cursor-pointer transition-colors hover:bg-mit-red-dark" onClick={startCamera}>
                重試
              </button>
            </div>
          ) : capturedImage ? (
            <div className="w-full max-w-full border-2 border-gray-200 rounded-lg overflow-hidden bg-black">
              <img src={capturedImage} alt="拍攝的照片" className="w-full h-auto block" />
            </div>
          ) : (
            <div className="w-full max-w-full border-2 border-gray-200 rounded-lg overflow-hidden bg-black">
              <video
                ref={videoRef}
                autoPlay
                playsInline
                className="w-full h-auto block scale-x-[-1]"
              />
            </div>
          )}
        </div>

        <div className="flex gap-3 py-5 px-6 border-t border-gray-200 justify-center">
          {capturedImage ? (
            <>
              <button className="py-3 px-6 border-none rounded-lg text-sm font-medium cursor-pointer transition-all font-sans bg-gray-100 text-gray-700 border border-gray-200 flex-1 hover:bg-gray-200" onClick={handleRetake}>
                重新拍攝
              </button>
              <button className="py-3 px-6 border-none rounded-lg text-sm font-medium cursor-pointer transition-all font-sans bg-mit-red text-white flex-1 hover:bg-mit-red-dark hover:-translate-y-0.5 hover:shadow-[0_4px_12px_rgba(214,69,69,0.3)] active:translate-y-0" onClick={handleUsePhoto}>
                使用此照片
              </button>
            </>
          ) : (
            <button className="py-3 px-6 border-none rounded-lg text-sm font-medium cursor-pointer transition-all font-sans bg-mit-red text-white w-full max-w-[200px] hover:bg-mit-red-dark hover:-translate-y-0.5 hover:shadow-[0_4px_12px_rgba(214,69,69,0.3)] active:translate-y-0" onClick={handleCapture}>
              拍攝
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default CameraModal;

