def buildFontCache():
    import matplotlib
    matplotlib
    matplotlib.use('AGG')
    from matplotlib import pyplot as plt
    plt.plot([0],[0])
    plt.show()
    plt.clf()

