import { motion } from "framer-motion";

import arshadPhoto from "../assets/team/arshad.jpeg";
import atharvPhoto from "../assets/team/atharv.jpeg";
import varunPhoto from "../assets/team/varun.png.jpeg";

function Team() {
  const members = [
    {
      name: "Varun Manoj",
      role: "Frontend Developer & UI/UX",
      photo: varunPhoto,
      responsibilities: [
        "React development",
        "Tailwind CSS",
        "Website design",
        "User Interface",
      ],
    },

    {
      name: "Arshad Ahemad Khan",
      role: "Backend Developer",
      photo: arshadPhoto,
      responsibilities: [
        "FastAPI",
        "API development",
        "Database",
        "Server integration",
      ],
    },

    {
      name: "Atharv Vijay Kudale",
      role: "AI/ML Engineer",
      photo: atharvPhoto,
      responsibilities: [
        "Basic Pitch",
        "MT3",
        "Music transcription",
        "AI pipeline",
      ],
    },
  ];

  return (
    <section id="team" className="py-24 px-8">
      <div className="max-w-7xl mx-auto">

        {/* Section Heading */}
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.7 }}
          className="text-center mb-16"
        >
          <h2 className="text-5xl font-bold">
            Meet The Team
          </h2>

          <p className="text-gray-400 mt-4">
            The minds building Maestro AI.
          </p>
        </motion.div>

        {/* Team Cards */}
        <div className="grid md:grid-cols-3 gap-8">

          {members.map((member, index) => (
            <motion.div
              key={index}
              initial={{
                opacity: 0,
                y: 50,
              }}
              whileInView={{
                opacity: 1,
                y: 0,
              }}
              viewport={{ once: true }}
              transition={{
                duration: 0.6,
                delay: index * 0.15,
              }}
              whileHover={{
                y: -10,
              }}
              className="
                group
                relative
                bg-[#111111]
                border
                border-white/10
                rounded-3xl
                p-8
                text-center
                overflow-hidden
                transition-all
                duration-300
                hover:border-purple-500/50
                hover:shadow-[0_0_40px_rgba(168,85,247,0.15)]
              "
            >

              {/* Background Glow */}
              <div
                className="
                  absolute
                  inset-0
                  bg-purple-500/10
                  blur-3xl
                  opacity-0
                  group-hover:opacity-100
                  transition-opacity
                  duration-500
                "
              />

              {/* Profile Photo */}
              <div
                className="
                  relative
                  w-36
                  h-36
                  mx-auto
                  rounded-full
                  overflow-hidden
                  border-2
                  border-purple-500/40
                  bg-[#050505]
                  group-hover:border-purple-400
                  group-hover:shadow-[0_0_30px_rgba(168,85,247,0.3)]
                  transition-all
                  duration-300
                "
              >
                <img
                  src={member.photo}
                  alt={member.name}
                  className="
                    w-full
                    h-full
                    object-cover
                    transition-transform
                    duration-500
                    group-hover:scale-110
                  "
                />
              </div>

              {/* Name */}
              <h3
                className="
                  relative
                  text-2xl
                  font-bold
                  mt-6
                "
              >
                {member.name}
              </h3>

              {/* Role */}
              <p
                className="
                  relative
                  text-cyan-400
                  mt-2
                  font-medium
                "
              >
                {member.role}
              </p>

              {/* Responsibilities */}
              <ul
                className="
                  relative
                  text-gray-400
                  text-sm
                  mt-6
                  space-y-2
                "
              >
                {member.responsibilities.map((item, i) => (
                  <li key={i}>
                    • {item}
                  </li>
                ))}
              </ul>

            </motion.div>
          ))}

        </div>
      </div>
    </section>
  );
}

export default Team;