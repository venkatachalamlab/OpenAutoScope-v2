import setuptools

requirements = [
    'docopt',
    'numpy',
    'pyzmq'
]

console_scripts = [
    'oas_hub=openautoscopev2.devices.hub_relay:main',
    'oas_forwarder=openautoscopev2.zmq.forwarder:main',
    'oas_processor=openautoscopev2.devices.processor:main',
    'oas_commands=openautoscopev2.devices.commands:main',
    'flir_camera=openautoscopev2.devices.flir_camera:main',
    'oas_data_hub=openautoscopev2.devices.data_hub:main',
    'oas_writer=openautoscopev2.devices.writer:main',
    'oas_logger=openautoscopev2.devices.logger:main',
    'oas_tracker=openautoscopev2.devices.tracker:main',
    'oas_teensy_commands=openautoscopev2.devices.teensy_commands:main',
    'oas=run_gui',
]

setuptools.setup(
    name="oas",
    version="0.1.0",
    author="Mahdi Torkashvand, Sina Rasouli",
    author_email="mmt.mahdi@gmail.com, rasoolibox193@gmail.com",
    description="Software to operate OpenAutoscope-v2",
    url="https://github.com/venkatachalamlab/OpenAutoScope-v2",
    project_urls={
        "Bug Tracker": "https://github.com/venkatachalamlab/OpenAutoScope-v2/issues",
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: Microsoft :: Windows :: Windows 10",
    ],
    entry_points={
        'console_scripts': console_scripts
    },
    packages=['openautoscopev2'],
    python_requires=">=3.6",
)
