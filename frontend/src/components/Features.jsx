import {
  Piano,
  Guitar,
  Waves,
  Drum,
  FileMusic,
  Sparkles,
} from "lucide-react";

import StaggerContainer, {
  StaggerItem,
} from "./StaggerContainer";

function Features() {
  const features = [
    {
      icon: Piano,
      title: "Piano",
      description:
        "Generate piano notations from audio recordings(implemented in future updates)  .",
    },
    {
      icon: Guitar,
      title: "Guitar",
      description:
        "Convert songs into playable guitar arrangements(implemented in future updates).",
    },
    {
      icon: Waves,
      title: "Flute",
      description:
        "Create melody-focused notation for flute performances.",
    },
    {
      icon: Drum,
      title: "Tabla",
      description:
        "Experimental AI-powered Indian percussion transcription(implemented in future updates).",
    },
    {
      icon: FileMusic,
      title: "Sheet Export",
      description:
        "Export generated music as PDF, MIDI and MusicXML.",
    },
    {
      icon: Sparkles,
      title: "AI Models",
      description:
        "Powered by modern music transcription models.",
    },
  ];

  return (
    <section
      id="features"
      className="relative max-w-7xl mx-auto px-8 py-28"
    >
      {/* Section Heading */}
      <StaggerContainer className="text-center max-w-3xl mx-auto mb-16">
        <StaggerItem>
          <p className="text-sm uppercase tracking-[0.2em] text-purple-400 mb-4">
            Capabilities
          </p>
        </StaggerItem>

        <StaggerItem>
          <h2 className="text-4xl md:text-5xl font-bold text-white">
            Powerful AI Music Features
          </h2>
        </StaggerItem>

        <StaggerItem>
          <p className="mt-5 text-gray-400 text-lg leading-8">
            Transform audio into structured musical notation with
            intelligent transcription tools built for modern musicians.
          </p>
        </StaggerItem>
      </StaggerContainer>

      {/* Feature Grid */}
      <StaggerContainer
        className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"
        stagger={0.1}
      >
        {features.map((item) => {
          const Icon = item.icon;

          return (
            <StaggerItem key={item.title}>
              <div
                className="
                  group
                  relative
                  h-full
                  overflow-hidden
                  rounded-3xl
                  border
                  border-white/10
                  bg-[#111111]
                  p-8
                  transition-all
                  duration-500
                  hover:-translate-y-2
                  hover:border-purple-500/40
                  hover:bg-[#141414]
                  hover:shadow-[0_20px_60px_rgba(139,92,246,0.12)]
                "
              >
                {/* Hover Glow */}
                <div
                  className="
                    absolute
                    -right-16
                    -top-16
                    h-32
                    w-32
                    rounded-full
                    bg-purple-500/10
                    blur-3xl
                    opacity-0
                    transition-opacity
                    duration-500
                    group-hover:opacity-100
                  "
                />

                {/* Icon */}
                <div
                  className="
                    relative
                    mb-7
                    flex
                    h-12
                    w-12
                    items-center
                    justify-center
                    rounded-xl
                    border
                    border-purple-400/20
                    bg-purple-500/10
                    transition-all
                    duration-500
                    group-hover:border-purple-400/40
                    group-hover:bg-purple-500/15
                  "
                >
                  <Icon
                    size={24}
                    className="
                      text-purple-400
                      transition-transform
                      duration-500
                      group-hover:scale-110
                    "
                  />
                </div>

                {/* Content */}
                <div className="relative">
                  <h3 className="text-xl font-semibold text-white">
                    {item.title}
                  </h3>

                  <p className="mt-3 text-sm leading-7 text-gray-400">
                    {item.description}
                  </p>
                </div>

                {/* Bottom Accent */}
                <div
                  className="
                    absolute
                    bottom-0
                    left-8
                    right-8
                    h-px
                    origin-left
                    scale-x-0
                    bg-gradient-to-r
                    from-purple-500
                    to-cyan-400
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
    </section>
  );
}

export default Features;
