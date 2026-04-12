import os
import glob
import librosa
import soundfile as sf
import numpy as np
import csv

def segment_audio(training_dir="training", output_dir="segmented", csv_path="segments.csv"):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    wav_files = sorted(glob.glob(os.path.join(training_dir, "*.wav")))
    total_files = len(wav_files)

    with open(csv_path, mode='w', newline='') as csv_file:
        csv_writer = csv.writer(csv_file)

        for idx, wav_file in enumerate(wav_files, start=1):
            file_name = os.path.basename(wav_file)
            print(f"Processing {idx}/{total_files}: {file_name}")
            base_name, ext = os.path.splitext(file_name)

            # Load the audio
            y, sr = librosa.load(wav_file, sr=None)

            # Use RMS energy to find prominent sections
            # Frame length and hop length can be adjusted based on the audio characteristics
            frame_length = 2048
            hop_length = 512
            rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]

            # Thresholding: e.g., anything above a certain threshold is considered prominent
            # Using a dynamic threshold based on the mean and standard deviation of RMS
            # Lowering the threshold to be less strict for short files
            threshold = np.mean(rms) + 0.1 * np.std(rms)

            prominent_frames = np.where(rms > threshold)[0]

            if len(prominent_frames) == 0:
                continue

            # Group contiguous frames into segments
            # A jump of more than a few frames means a new segment
            min_gap = int(0.2 * sr / hop_length) # 0.2 second gap allowed
            if min_gap < 5:
                min_gap = 5
            segments = []
            current_segment = [prominent_frames[0]]

            for i in range(1, len(prominent_frames)):
                if prominent_frames[i] - prominent_frames[i-1] > min_gap:
                    segments.append(current_segment)
                    current_segment = [prominent_frames[i]]
                else:
                    current_segment.append(prominent_frames[i])
            segments.append(current_segment)

            # Filter out segments shorter than 1 second
            min_segment_frames = int(1.0 * sr / hop_length)
            segments = [seg for seg in segments if len(seg) > min_segment_frames]

            # Buffer duration in seconds
            buffer_seconds = 0.5
            buffer_samples = int(buffer_seconds * sr)

            for idx, seg in enumerate(segments):
                start_frame = seg[0]
                end_frame = seg[-1]

                # Convert frame indices back to sample indices
                start_sample = start_frame * hop_length
                end_sample = end_frame * hop_length + frame_length

                # Add buffer and ensure we stay within array bounds
                start_sample = max(0, start_sample - buffer_samples)
                end_sample = min(len(y), end_sample + buffer_samples)

                # Extract segment
                y_segment = y[start_sample:end_sample]

                # Save segment
                segment_name = f"{base_name}_seg{idx+1:03d}{ext}"
                segment_path = os.path.join(output_dir, segment_name)

                sf.write(segment_path, y_segment, sr)

                # Write to CSV
                csv_writer.writerow([file_name, segment_name])

    print(f"Segmentation complete. Results saved in {output_dir} and {csv_path}")

if __name__ == "__main__":
    segment_audio()
