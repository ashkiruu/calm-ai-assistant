using System;
using System.IO;
using System.Text;
using UnityEngine;

namespace CALM.Assistant
{
    /// <summary>
    /// Turns a recorded clip into WAV bytes. Unity can record audio and play it
    /// but cannot write a file format, so this exists to hand the transcriber
    /// something it can read.
    ///
    /// 16-bit PCM mono: what Whisper wants, and the smallest thing that carries
    /// a child's voice faithfully.
    /// </summary>
    public static class CalmWav
    {
        const int BitsPerSample = 16;
        const int HeaderBytes = 44;
        /// Samples arrive as floats in [-1, 1]; this is the 16-bit signed range.
        const float FullScale = 32767f;

        /// <summary>
        /// Encode the first <paramref name="sampleCount"/> samples of a clip.
        ///
        /// The count matters. Microphone.Start allocates the whole buffer up
        /// front, so a clip holding a two second question is mostly silence.
        /// Sending that silence is not merely wasteful: Whisper invents speech
        /// to fill it, and an invented question reaches the router looking
        /// exactly like a real one.
        /// </summary>
        public static byte[] Encode(AudioClip clip, int sampleCount)
        {
            if (clip == null) throw new ArgumentNullException(nameof(clip));

            sampleCount = Mathf.Clamp(sampleCount, 0, clip.samples);
            var samples = new float[sampleCount * clip.channels];
            if (sampleCount > 0)
            {
                clip.GetData(samples, 0);
            }
            return Encode(samples, clip.channels, clip.frequency);
        }

        public static byte[] Encode(float[] samples, int channels, int frequency)
        {
            int dataBytes = samples.Length * sizeof(short);
            var stream = new MemoryStream(HeaderBytes + dataBytes);

            using (var writer = new BinaryWriter(stream, Encoding.UTF8, true))
            {
                int byteRate = frequency * channels * BitsPerSample / 8;

                writer.Write(Encoding.ASCII.GetBytes("RIFF"));
                writer.Write(36 + dataBytes);
                writer.Write(Encoding.ASCII.GetBytes("WAVE"));

                writer.Write(Encoding.ASCII.GetBytes("fmt "));
                writer.Write(16);                                    // chunk size
                writer.Write((short)1);                              // PCM
                writer.Write((short)channels);
                writer.Write(frequency);
                writer.Write(byteRate);
                writer.Write((short)(channels * BitsPerSample / 8)); // block align
                writer.Write((short)BitsPerSample);

                writer.Write(Encoding.ASCII.GetBytes("data"));
                writer.Write(dataBytes);

                foreach (float sample in samples)
                {
                    // Clamp before scaling: a sample slightly outside the range
                    // wraps to full-scale noise once cast, which sounds like a
                    // click and reads to the transcriber as a consonant.
                    writer.Write((short)(Mathf.Clamp(sample, -1f, 1f) * FullScale));
                }
            }
            return stream.ToArray();
        }

        /// <summary>
        /// Peak amplitude, used to tell a real question from an empty room.
        /// </summary>
        public static float PeakLevel(AudioClip clip, int sampleCount)
        {
            if (clip == null || sampleCount <= 0) return 0f;

            sampleCount = Mathf.Clamp(sampleCount, 0, clip.samples);
            var samples = new float[sampleCount * clip.channels];
            clip.GetData(samples, 0);

            float peak = 0f;
            foreach (float sample in samples)
            {
                float magnitude = Mathf.Abs(sample);
                if (magnitude > peak) peak = magnitude;
            }
            return peak;
        }
    }
}
