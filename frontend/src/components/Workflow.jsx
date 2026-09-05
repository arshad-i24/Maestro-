import { Upload, Brain, Music, FileMusic, Download } from "lucide-react";
import StaggerContainer, {
  StaggerItem,
} from "./StaggerContainer";

function Workflow() {
  const steps = [
    {
      icon: Upload,
      title: "Upload Audio",
      description: "Upload MP3, WAV or FLAC music files.",
    },
    {
      icon: Brain,
      title: "AI Processing",
      description: 
        "AI models analyze audio patterns and instruments.",
    },
    {
      icon: Music,
      title: "Music Transcription",
      description:
        "Convert audio into MIDI and musical data.",
    },
    {
      icon: FileMusic,
      title: "Notation Generation",
      description:
        "Generate readable sheet music notation.",
    },
    {
      icon: Download,
      title: "Export",
      description:
        "Download PDF, MIDI and MusicXML files.",
    },
  ];

  return (
    <section
      id="workflow"
      className="relative px-8 py-28"
    >
      <div className="max-w-7xl mx-auto">

        {/* Section Heading */}
        <StaggerContainer className="mx-auto mb-16 max-w-3xl text-center">
          <StaggerItem>
            <p className="mb-4 text-sm uppercase tracking-[0.2em] text-purple-400">
              The Process
            </p>
          </StaggerItem>

          <StaggerItem>
            <h2 className="text-4xl font-bold text-white md:text-5xl">
              How Maestro Works
            </h2>
          </StaggerItem>

          <StaggerItem>
            <p className="mt-5 text-lg leading-8 text-gray-400">
              From audio input to downloadable sheet music through a
              streamlined AI workflow.
            </p>
          </StaggerItem>
        </StaggerContainer>

        {/* Workflow */}
        <StaggerContainer
          className="relative grid grid-cols-1 gap-6 md:grid-cols-5"
          stagger={0.14}
        >
          {/* Connecting Line */}
          <div className="absolute left-[10%] right-[10%] top-14 hidden h-px bg-gradient-to-r from-purple-500/10 via-purple-400/40 to-cyan-400/10 md:block" />

          {steps.map((step, index) => {
            const Icon = step.icon;

            return (
              <StaggerItem key={step.title}>
                <div
                  className="
                    group
                    relative
                    h-full
                    rounded-2xl
                    border
                    border-white/10
                    bg-[#111111]
                    p-6
                    text-center
                    transition-all
                    duration-500
                    hover:-translate-y-2
                    hover:border-purple-500/40
                    hover:bg-[#141414]
                    hover:shadow-[0_20px_50px_rgba(139,92,246,0.10)]
                  "
                >
                  {/* Step Number */}
                  <div
                    className="
                      absolute
                      right-4
                      top-4
                      text-xs
                      font-medium
                      text-gray-600
                      transition-colors
                      duration-300
                      group-hover:text-purple-400
                    "
                  >
                    0{index + 1}
                  </div>

                  {/* Icon */}
                  <div
                    className="
                      relative
                      mx-auto
                      flex
                      h-16
                      w-16
                      items-center
                      justify-center
                      rounded-2xl
                      border
                      border-cyan-400/10
                      bg-cyan-400/5
                      transition-all
                      duration-500
                      group-hover:border-purple-400/30
                      group-hover:bg-purple-500/10
                      group-hover:shadow-[0_0_25px_rgba(139,92,246,0.12)]
                    "
                  >
                    <Icon
                      size={30}
                      className="
                        text-cyan-400
                        transition-all
                        duration-500
                        group-hover:scale-110
                        group-hover:text-purple-400
                      "
                    />

                    {/* Connection Dot */}
                    {index < steps.length - 1 && (
                      <div
                        className="
                          absolute
                          -right-[25px]
                          top-1/2
                          hidden
                          h-2
                          w-2
                          -translate-y-1/2
                          rounded-full
                          bg-purple-400/50
                          md:block
                        "
                      />
                    )}
                  </div>

                  {/* Title */}
                  <h3 className="mt-6 text-lg font-semibold text-white">
                    {step.title}
                  </h3>

                  {/* Description */}
                  <p className="mt-3 text-sm leading-6 text-gray-400">
                    {step.description}
                  </p>

                  {/* Bottom Accent */}
                  <div
                    className="
                      absolute
                      bottom-0
                      left-6
                      right-6
                      h-px
                      origin-center
                      scale-x-0
                      bg-gradient-to-r
                      from-transparent
                      via-purple-400
                      to-transparent
                      transition-transform
                      duration-500
                      group-hover:scale-x-100
                    "
                  />
                </div>
              </StaggerItem>
            );
          })}
        </StaggerContainer>

      </div>
    </section>
  );
}

export default Workflow;