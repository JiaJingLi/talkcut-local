class VideoPlayer {
    constructor(videoElement) {
        this.video = videoElement;
        this.currentTime = 0;
        this.duration = 0;

        this.video.addEventListener('timeupdate', () => {
            this.currentTime = this.video.currentTime;
            if (this.onTimeUpdate) {
                this.onTimeUpdate(this.currentTime);
            }
        });

        this.video.addEventListener('loadedmetadata', () => {
            this.duration = this.video.duration;
            if (this.onLoaded) {
                this.onLoaded(this.duration);
            }
        });
    }

    load(src) {
        this.video.src = src;
    }

    play() {
        this.video.play();
    }

    pause() {
        this.video.pause();
    }

    seek(time) {
        this.video.currentTime = time;
    }

    setOnTimeUpdate(callback) {
        this.onTimeUpdate = callback;
    }

    setOnLoaded(callback) {
        this.onLoaded = callback;
    }
}
