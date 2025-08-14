/**
 * Voice dictation functionality for Memoria Hub
 * Implements press-and-hold recording with MediaRecorder,
 * uploads audio to /transcribe, and on success posts to /memories.
 */

class VoiceDictation {
  constructor() {
    this.mediaRecorder = null;
    this.audioChunks = [];
    this.isRecording = false;
    this.micButton = null;
    this.statusElement = null;
    this.onTranscriptionSuccess = null;
    this.onError = null;
  }

  async init(micButtonId, statusElementId, onSuccess, onError) {
    this.micButton = document.getElementById(micButtonId);
    this.statusElement = document.getElementById(statusElementId);
    this.onTranscriptionSuccess = onSuccess;
    this.onError = onError;

    if (!this.micButton) {
      console.error('Mic button not found');
      return false;
    }

    // Check for MediaRecorder support
    if (!navigator.mediaDevices || !window.MediaRecorder) {
      this.handleError('Voice recording not supported in this browser');
      return false;
    }

    // Set up event listeners
    this.setupEventListeners();
    return true;
  }

  setupEventListeners() {
    // Mouse events
    this.micButton.addEventListener('mousedown', (e) => {
      e.preventDefault();
      this.startRecording();
    });

    this.micButton.addEventListener('mouseup', (e) => {
      e.preventDefault();
      this.stopRecording();
    });

    this.micButton.addEventListener('mouseleave', (e) => {
      if (this.isRecording) {
        this.stopRecording();
      }
    });

    // Touch events for mobile
    this.micButton.addEventListener('touchstart', (e) => {
      e.preventDefault();
      this.startRecording();
    });

    this.micButton.addEventListener('touchend', (e) => {
      e.preventDefault();
      this.stopRecording();
    });

    this.micButton.addEventListener('touchcancel', (e) => {
      if (this.isRecording) {
        this.stopRecording();
      }
    });

    // Prevent context menu
    this.micButton.addEventListener('contextmenu', (e) => {
      e.preventDefault();
    });
  }

  async startRecording() {
    if (this.isRecording) return;

    try {
      // Request microphone permission
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        } 
      });

      this.audioChunks = [];
      this.mediaRecorder = new MediaRecorder(stream, {
        mimeType: this.getSupportedMimeType()
      });

      this.mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          this.audioChunks.push(event.data);
        }
      };

      this.mediaRecorder.onstop = () => {
        this.processRecording();
        // Stop all tracks to release the microphone
        stream.getTracks().forEach(track => track.stop());
      };

      this.mediaRecorder.start();
      this.isRecording = true;
      
      // Update UI
      this.micButton.classList.add('recording');
      this.updateStatus('Recording... Release to stop');

    } catch (error) {
      if (error.name === 'NotAllowedError' || error.name === 'PermissionDeniedError') {
        this.handleError('Microphone permission denied. Please allow microphone access and try again.');
      } else if (error.name === 'NotFoundError') {
        this.handleError('No microphone found. Please check your microphone connection.');
      } else {
        this.handleError(`Failed to start recording: ${error.message}`);
      }
    }
  }

  stopRecording() {
    if (!this.isRecording || !this.mediaRecorder) return;

    this.isRecording = false;
    this.mediaRecorder.stop();
    
    // Update UI
    this.micButton.classList.remove('recording');
    this.updateStatus('Processing...');
  }

  getSupportedMimeType() {
    const types = [
      'audio/webm;codecs=opus',
      'audio/webm',
      'audio/mp4',
      'audio/wav'
    ];
    
    for (const type of types) {
      if (MediaRecorder.isTypeSupported(type)) {
        return type;
      }
    }
    
    return 'audio/webm'; // Fallback
  }

  async processRecording() {
    if (this.audioChunks.length === 0) {
      this.handleError('No audio recorded');
      return;
    }

    try {
      // Create blob from audio chunks
      const audioBlob = new Blob(this.audioChunks, { type: this.getSupportedMimeType() });
      
      // Show transcribing status
      this.updateStatus('Transcribing...');

      // Upload to transcribe endpoint
      const formData = new FormData();
      formData.append('audio', audioBlob, 'recording.webm');

      const response = await fetch('/transcribe', {
        method: 'POST',
        headers: {
          ...(window.PASS ? {'x-auth-token': window.PASS} : {})
        },
        body: formData
      });

      if (response.status === 401) {
        this.handleError('Unauthorized. Please check your passcode.');
        return;
      }

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText);
      }

      const result = await response.json();
      const transcribedText = result.text;

      if (!transcribedText || transcribedText.trim() === '') {
        this.handleError('No speech detected. Please try again.');
        return;
      }

      // Clear status
      this.clearStatus();

      // Call success callback with transcribed text
      if (this.onTranscriptionSuccess) {
        await this.onTranscriptionSuccess(transcribedText);
      }

    } catch (error) {
      this.handleError(`Transcription failed: ${error.message}`);
    }
  }

  updateStatus(message) {
    if (this.statusElement) {
      this.statusElement.textContent = message;
      this.statusElement.style.display = 'block';
    }
  }

  clearStatus() {
    if (this.statusElement) {
      this.statusElement.style.display = 'none';
      this.statusElement.textContent = '';
    }
  }

  handleError(message) {
    console.error('Voice dictation error:', message);
    this.clearStatus();
    
    if (this.onError) {
      this.onError(message);
    }
  }
}

// Export for use in other scripts
window.VoiceDictation = VoiceDictation;